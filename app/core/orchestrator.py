"""Pipeline orchestrator for coordinating stages."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.storage.sqlite import Database
from app.core.project_manager import ProjectManager
from app.core.stage_executor import StageExecutor
from app.core.approval_service import ApprovalService
from app.core.artifact_registry import ArtifactRegistry
from app.core.cost_guardrail import CostGuardrail
from app.core.quality_gate import QualityGateRunner
from app.domain.enums import ProjectStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Stage order for pipeline execution
STAGE_ORDER = [
    "intake",
    "benchmark",
    "script",
    "voice",
    "storyboard",
    "assets",
    "render",
]

# Approval checkpoints that pause execution
APPROVAL_CHECKPOINTS = {
    "script": "script",
    "storyboard": "storyboard",
}


class PipelineOrchestrator:
    """Orchestrates pipeline execution."""

    def __init__(
        self,
        db: Database,
        cost_guardrail: CostGuardrail,
        config: dict,
        settings=None,
    ):
        """Initialize orchestrator."""
        self.db = db
        self.config = config
        self.settings = settings
        self.cost_guardrail = cost_guardrail

        # Initialize sub-managers
        self.projects = ProjectManager(db)
        self.executor = StageExecutor(db)
        self.approvals = ApprovalService(db)
        self.artifacts = ArtifactRegistry(db)
        self.quality_gate = QualityGateRunner()

    async def initialize(self):
        """Initialize database."""
        await self.db.init()

    async def shutdown(self):
        """Close database connection."""
        await self.db.close()

    def _get_workspace_root(self) -> str:
        """Get workspace root path."""
        if self.settings:
            return self.settings.workspace_root
        return self.config.get("workspace_root", "workspace")

    def _create_providers(self):
        """Create provider instances based on settings."""
        from app.providers.research import YouTubeResearchProvider
        from app.providers.narrative import AnthropicNarrativeProvider
        from app.providers.tts import EdgeTTSProvider
        from app.providers.stt import OpenAISTTProvider
        from app.providers.asset import OpenAIAssetProvider

        api_keys = {}
        if self.settings:
            api_keys = {
                "youtube_api_key": self.settings.youtube_api_key,
                "anthropic_api_key": self.settings.anthropic_api_key,
                "openai_api_key": self.settings.openai_api_key,
            }

        workspace_root = self._get_workspace_root()

        research = YouTubeResearchProvider(
            api_key=api_keys.get("youtube_api_key", ""),
            anthropic_api_key=api_keys.get("anthropic_api_key", ""),
        )
        narrative = AnthropicNarrativeProvider(
            api_key=api_keys.get("anthropic_api_key", ""),
            workspace_root=workspace_root,
        )
        tts = EdgeTTSProvider(workspace_root=workspace_root)
        stt = OpenAISTTProvider(
            api_key=api_keys.get("openai_api_key", ""),
        )
        asset = OpenAIAssetProvider(
            api_key=api_keys.get("openai_api_key", ""),
            workspace_root=workspace_root,
        )

        return {
            "research": research,
            "narrative": narrative,
            "tts": tts,
            "stt": stt,
            "asset": asset,
        }

    async def run_stage(
        self,
        slug: str,
        stage_name: str,
        mode: str = "resume",
        run_id: Optional[str] = None,
        approve_all: bool = False,
    ) -> dict:
        """Run a single stage for a project.

        Args:
            slug: Project slug
            stage_name: Stage to run
            mode: Execution mode (skip, resume, overwrite)
            run_id: Optional run ID (generates new if None)
            approve_all: Auto-approve non-upload checkpoints

        Returns:
            dict with stage execution results
        """
        project = await self.projects.get(slug)
        if not project:
            raise ValueError(f"Project not found: {slug}")

        if not run_id:
            run_id = f"run_{uuid.uuid4().hex[:12]}"

        workspace_root = self._get_workspace_root()
        project_dir = Path(workspace_root) / "projects" / slug
        providers = self._create_providers()

        logger.info(
            "Running stage",
            slug=slug,
            stage=stage_name,
            mode=mode,
            run_id=run_id,
        )

        result = await self._execute_stage(
            project=project,
            stage_name=stage_name,
            project_dir=project_dir,
            providers=providers,
            run_id=run_id,
            workspace_root=workspace_root,
        )

        logger.info(
            "Stage completed",
            slug=slug,
            stage=stage_name,
            success=result.get("success", False),
        )

        return result

    async def run_pipeline(
        self,
        slug: str,
        from_stage: Optional[str] = None,
        until_stage: Optional[str] = None,
        mode: str = "resume",
        run_id: Optional[str] = None,
        approve_all: bool = False,
    ) -> dict:
        """Run pipeline (multiple stages) for a project.

        Args:
            slug: Project slug
            from_stage: Start from this stage (default: first)
            until_stage: Stop after this stage (default: last)
            mode: Execution mode
            run_id: Optional run ID
            approve_all: Auto-approve non-upload checkpoints

        Returns:
            dict with pipeline execution results
        """
        project = await self.projects.get(slug)
        if not project:
            raise ValueError(f"Project not found: {slug}")

        if not run_id:
            run_id = f"run_{uuid.uuid4().hex[:12]}"

        # Determine stage range
        start_idx = 0
        end_idx = len(STAGE_ORDER) - 1

        if from_stage:
            if from_stage in STAGE_ORDER:
                start_idx = STAGE_ORDER.index(from_stage)
            else:
                raise ValueError(f"Unknown stage: {from_stage}")

        if until_stage:
            if until_stage in STAGE_ORDER:
                end_idx = STAGE_ORDER.index(until_stage)
            else:
                raise ValueError(f"Unknown stage: {until_stage}")

        stages_to_run = STAGE_ORDER[start_idx:end_idx + 1]

        workspace_root = self._get_workspace_root()
        project_dir = Path(workspace_root) / "projects" / slug
        providers = self._create_providers()

        logger.info(
            "Running pipeline",
            slug=slug,
            stages=stages_to_run,
            run_id=run_id,
        )

        results = {}
        for stage_name in stages_to_run:
            # Check if approval is needed before this stage
            if stage_name in APPROVAL_CHECKPOINTS and not approve_all:
                checkpoint = APPROVAL_CHECKPOINTS[stage_name]
                logger.info(
                    "Approval checkpoint reached",
                    stage=stage_name,
                    checkpoint=checkpoint,
                )
                results[stage_name] = {
                    "success": False,
                    "status": "awaiting_approval",
                    "checkpoint": checkpoint,
                    "message": f"Approval required for '{checkpoint}'. Use 'yt approve <id>' to continue.",
                }
                break

            try:
                result = await self._execute_stage(
                    project=project,
                    stage_name=stage_name,
                    project_dir=project_dir,
                    providers=providers,
                    run_id=run_id,
                    workspace_root=workspace_root,
                )
                results[stage_name] = result

                if not result.get("success", False):
                    logger.error(
                        "Stage failed, stopping pipeline",
                        stage=stage_name,
                        error=result.get("error"),
                    )
                    break

                logger.info("Stage succeeded", stage=stage_name)

            except Exception as e:
                logger.error(
                    "Stage exception, stopping pipeline",
                    stage=stage_name,
                    error=str(e),
                )
                results[stage_name] = {
                    "success": False,
                    "error": str(e),
                }
                break

        return {
            "run_id": run_id,
            "stages": results,
            "completed": all(r.get("success", False) for r in results.values()),
        }

    async def _execute_stage(
        self,
        project,
        stage_name: str,
        project_dir: Path,
        providers: dict,
        run_id: str,
        workspace_root: str,
    ) -> dict:
        """Execute a single stage with proper provider wiring.

        Returns:
            dict with success status and result/error
        """
        try:
            if stage_name == "intake":
                from app.stages.stage0_intake import IntakeStage

                stage = IntakeStage(db=self.db, workspace_root=workspace_root)
                result = await stage.execute(project)
                return {"success": True, "result": f"Workspace created: {project.slug}"}

            elif stage_name == "benchmark":
                from app.stages.stage1_benchmark import BenchmarkStage, BenchmarkStageInput

                # Use niche + title_seed as search keywords
                search_keywords = [project.niche, project.title_seed]
                stage = BenchmarkStage(db=self.db)
                input_data = BenchmarkStageInput(
                    project=project,
                    search_keywords=search_keywords,
                    workspace_root=workspace_root,
                    youtube_api_key=self.settings.youtube_api_key if self.settings else "",
                    anthropic_api_key=self.settings.anthropic_api_key if self.settings else None,
                )
                result = await stage.execute(input_data)
                return {"success": True, "result": "BenchmarkReport generated"}

            elif stage_name == "script":
                from app.stages.stage2_script import ScriptStage, ScriptStageInput

                benchmark_path = str(project_dir / "01_benchmark" / "benchmark_report.json")
                stage = ScriptStage(db=self.db)
                input_data = ScriptStageInput(
                    project=project,
                    benchmark_report_path=benchmark_path,
                    workspace_root=workspace_root,
                    anthropic_api_key=self.settings.anthropic_api_key if self.settings else None,
                )
                result = await stage.execute(input_data)
                return {"success": True, "result": "ScriptContract generated"}

            elif stage_name == "voice":
                from app.stages.stage3_voice import VoiceStage, VoiceStageInput
                from app.storage.files import FileStorage

                script_path = project_dir / "02_script" / "script_contract.json"
                script_data = await FileStorage.load_json(str(script_path))
                if not script_data:
                    return {"success": False, "error": "ScriptContract not found. Run script first."}

                from app.domain.contracts import ScriptContract
                script_contract = ScriptContract(**script_data)

                stage = VoiceStage()
                input_data = VoiceStageInput(
                    script_contract=script_contract,
                    workspace_root=workspace_root,
                    openai_api_key=self.settings.openai_api_key if self.settings else None,
                )
                result = await stage.execute(input_data)
                return {"success": True, "result": "NarrationContract generated"}

            elif stage_name == "storyboard":
                from app.stages.stage4_storyboard import StoryboardStage, StoryboardStageInput
                from app.storage.files import FileStorage

                script_path = project_dir / "02_script" / "script_contract.json"
                narration_path = project_dir / "03_voice" / "narration_contract.json"

                script_data = await FileStorage.load_json(str(script_path))
                narration_data = await FileStorage.load_json(str(narration_path))

                if not script_data:
                    return {"success": False, "error": "ScriptContract not found."}
                if not narration_data:
                    return {"success": False, "error": "NarrationContract not found."}

                from app.domain.contracts import ScriptContract, NarrationContract
                script_contract = ScriptContract(**script_data)
                narration_contract = NarrationContract(**narration_data)

                stage = StoryboardStage(db=self.db)
                input_data = StoryboardStageInput(
                    script_contract=script_contract,
                    narration_contract=narration_contract,
                    workspace_root=workspace_root,
                    anthropic_api_key=self.settings.anthropic_api_key if self.settings else None,
                )
                result = await stage.execute(input_data)
                return {"success": True, "result": "StoryboardContract generated"}

            elif stage_name == "assets":
                from app.stages.stage5_assets import AssetStage, AssetStageInput
                from app.storage.files import FileStorage

                storyboard_path = project_dir / "04_storyboard" / "storyboard_contract.json"
                storyboard_data = await FileStorage.load_json(str(storyboard_path))

                if not storyboard_data:
                    return {"success": False, "error": "StoryboardContract not found."}

                from app.domain.contracts import StoryboardContract
                storyboard_contract = StoryboardContract(**storyboard_data)

                stage = AssetStage(db=self.db)
                input_data = AssetStageInput(
                    storyboard_contract=storyboard_contract,
                    workspace_root=workspace_root,
                    openai_api_key=self.settings.openai_api_key if self.settings else None,
                    stage_run_id=run_id,
                )
                result = await stage.execute(input_data)
                return {"success": True, "result": "AssetManifestContract generated"}

            elif stage_name == "render":
                from app.stages.stage6_render import RenderStage, RenderStageInput
                from app.storage.files import FileStorage

                narration_path = project_dir / "03_voice" / "narration_contract.json"
                storyboard_path = project_dir / "04_storyboard" / "storyboard_contract.json"
                manifest_path = project_dir / "05_assets" / "asset_manifest.json"

                narration_data = await FileStorage.load_json(str(narration_path))
                storyboard_data = await FileStorage.load_json(str(storyboard_path))
                manifest_data = await FileStorage.load_json(str(manifest_path))

                if not narration_data:
                    return {"success": False, "error": "NarrationContract not found."}
                if not storyboard_data:
                    return {"success": False, "error": "StoryboardContract not found."}
                if not manifest_data:
                    return {"success": False, "error": "AssetManifestContract not found."}

                from app.domain.contracts import (
                    NarrationContract, StoryboardContract, AssetManifestContract,
                )
                narration_contract = NarrationContract(**narration_data)
                storyboard_contract = StoryboardContract(**storyboard_data)
                asset_manifest = AssetManifestContract(**manifest_data)

                stage = RenderStage()
                input_data = RenderStageInput(
                    narration_contract=narration_contract,
                    storyboard_contract=storyboard_contract,
                    asset_manifest_contract=asset_manifest,
                    workspace_root=workspace_root,
                    stage_run_id=run_id,
                )
                result = await stage.execute(input_data)
                return {"success": True, "result": "draft.mp4 rendered"}

            else:
                return {"success": False, "error": f"Unknown stage: {stage_name}"}

        except Exception as e:
            logger.error(
                "Stage execution failed",
                stage=stage_name,
                error=str(e),
            )
            return {"success": False, "error": str(e)}
