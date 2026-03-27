"""Stage 2: Script generation."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.contracts import BenchmarkReport, ScriptContract
from app.domain.enums import ProjectStatus
from app.domain.models import Project, StageRun
from app.domain.schemas import ScriptRequest
from app.providers.narrative import AnthropicNarrativeProvider
from app.providers.base import ProviderCallContext
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.storage.sqlite import Database
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScriptStageInput:
    """Input data for script stage."""

    def __init__(
        self,
        project: Project,
        benchmark_report_path: str,
        workspace_root: str,
        anthropic_api_key: Optional[str] = None,
    ):
        """Initialize script stage input.

        Args:
            project: Project instance
            benchmark_report_path: Path to benchmark report JSON
            workspace_root: Workspace root directory
            anthropic_api_key: Optional Anthropic API key
        """
        self.project = project
        self.benchmark_report_path = benchmark_report_path
        self.workspace_root = workspace_root
        self.anthropic_api_key = anthropic_api_key


class ScriptStage(BaseStage):
    """Stage 2: Script generation with role separation.

    Pipeline:
    1. Strategist: Analyzes benchmark, picks angle, plans CTR strategy
    2. Writer: Writes full script draft with hook/body/CTA segments
    3. Reviewer: Evaluates script quality, suggests improvements
    4. If rejected by reviewer: one revision round with Writer

    Output:
    - script_contract.json (ScriptContract)
    - content_brief.md (human-readable strategy)
    - final_script.md (human-readable script)
    """

    stage_name = "script"

    def __init__(self, db: Database):
        """Initialize script stage.

        Args:
            db: Database connection
        """
        self.db = db

    async def execute(self, input_data: ScriptStageInput) -> ScriptContract:
        """Generate script with role separation pipeline.

        Creates:
        - script_contract.json (ScriptContract)
        - content_brief.md (human-readable)
        - final_script.md (human-readable)

        Args:
            input_data: Script stage input

        Returns:
            ScriptContract

        Raises:
            ValueError: If script generation fails
        """
        project = input_data.project
        workspace = Path(input_data.workspace_root) / "projects" / project.slug
        script_dir = workspace / "02_script"
        script_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Starting script generation",
            project_slug=project.slug,
            title_seed=project.title_seed,
        )

        # Create provider
        narrative_provider = AnthropicNarrativeProvider(
            api_key=input_data.anthropic_api_key,
            workspace_root=input_data.workspace_root,
        )

        # Create script request
        script_request = ScriptRequest(
            benchmark_report_path=input_data.benchmark_report_path,
            title_seed=project.title_seed,
            target_duration_sec=project.target_duration_sec,
            niche=project.niche,
            channel_voice={"tone": "friendly", "style": "educational"}
            if not hasattr(project, "channel_voice")
            else project.channel_voice,
        )

        # Create provider context
        ctx = ProviderCallContext(
            run_id=str(project.id),
            stage_run_id=f"stg_{project.id}_{self.stage_name}_1",
            attempt_no=1,
            idempotency_key=self._compute_idempotency_key(
                project.id, project.title_seed
            ),
        )

        try:
            # Estimate cost
            cost_estimate = await narrative_provider.estimate_script_cost(
                script_request, ctx
            )
            logger.info(
                "Script generation cost estimated",
                estimated_cost=cost_estimate.estimated_cost_usd,
            )

            # Generate script
            script_contract = await narrative_provider.generate_script(
                script_request, ctx
            )

            # Save script contract as JSON
            contract_json_path = script_dir / "script_contract.json"
            await FileStorage.save_json(
                str(contract_json_path),
                json.loads(script_contract.model_dump_json()),
            )

            # Convert to human-readable markdown
            final_script_md = self._format_script_markdown(script_contract)
            final_script_path = script_dir / "final_script.md"
            await FileStorage.save_text(str(final_script_path), final_script_md)

            # Create content brief markdown (strategy summary)
            content_brief_md = self._create_content_brief_markdown(script_contract)
            content_brief_path = script_dir / "content_brief.md"
            await FileStorage.save_text(str(content_brief_path), content_brief_md)

            logger.info(
                "Script generation completed",
                project_slug=project.slug,
                script_id=script_contract.contract_id,
                segment_count=len(script_contract.segments),
                total_duration=sum(s.est_duration_sec for s in script_contract.segments),
            )

            return script_contract

        except Exception as e:
            logger.error(
                "Script generation failed",
                project_slug=project.slug,
                error=str(e),
            )
            raise ValueError(f"Script generation failed: {str(e)}") from e

    def _compute_idempotency_key(self, project_id, title_seed: str) -> str:
        """Compute idempotency key for script execution.

        Args:
            project_id: Project ID
            title_seed: Title seed

        Returns:
            Idempotency key hash
        """
        content = f"{project_id}:{title_seed}:script_v1"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _format_script_markdown(self, contract: ScriptContract) -> str:
        """Format script contract as human-readable markdown.

        Args:
            contract: ScriptContract

        Returns:
            Markdown formatted script
        """
        md_lines = [
            f"# {contract.title}",
            "",
            f"**Target Duration**: {contract.target_duration_sec} seconds",
            f"**Language**: {contract.language}",
            f"**Generated**: {contract.created_at.isoformat()}",
            "",
            "---",
            "",
        ]

        # Add segments organized by purpose
        for segment in contract.segments:
            purpose_label = {
                "hook": "Hook (Opening)",
                "body": "Body (Main Content)",
                "cta": "Call-to-Action (Closing)",
            }.get(segment.purpose, segment.purpose.title())

            md_lines.extend(
                [
                    f"## {purpose_label}",
                    f"*Order: {segment.order} | Duration: {segment.est_duration_sec:.1f}s*",
                    "",
                    segment.text,
                    "",
                ]
            )

        # Summary statistics
        total_duration = sum(s.est_duration_sec for s in contract.segments)
        duration_deviation = (
            (total_duration - contract.target_duration_sec)
            / contract.target_duration_sec
            * 100
        )

        md_lines.extend(
            [
                "---",
                "",
                "## Script Statistics",
                "",
                f"- **Total Duration**: {total_duration:.1f} seconds",
                f"- **Target Duration**: {contract.target_duration_sec} seconds",
                f"- **Deviation**: {duration_deviation:+.1f}%",
                f"- **Segments**: {len(contract.segments)}",
                "",
                f"*Generated by Stage 2 (Script) - Run ID: {contract.run_id}*",
            ]
        )

        return "\n".join(md_lines)

    def _create_content_brief_markdown(self, contract: ScriptContract) -> str:
        """Create content strategy brief markdown.

        Args:
            contract: ScriptContract

        Returns:
            Markdown formatted content brief
        """
        md_lines = [
            "# Content Strategy Brief",
            "",
            "This document summarizes the content strategy and script structure generated for this video.",
            "",
            "## Video Information",
            "",
            f"- **Title**: {contract.title}",
            f"- **Target Duration**: {contract.target_duration_sec} seconds",
            f"- **Language**: {contract.language}",
            "",
            "## Script Structure",
            "",
        ]

        # Segment breakdown
        for segment in contract.segments:
            purpose_label = segment.purpose.upper()
            percentage = (
                (segment.est_duration_sec / contract.target_duration_sec) * 100
                if contract.target_duration_sec > 0
                else 0
            )
            md_lines.extend(
                [
                    f"### {purpose_label}",
                    f"**Duration**: {segment.est_duration_sec:.1f}s ({percentage:.1f}%)",
                    f"**Order**: {segment.order}",
                    "",
                    f"{segment.text[:100]}...",
                    "",
                ]
            )

        # Summary
        total_duration = sum(s.est_duration_sec for s in contract.segments)
        hook_segments = [s for s in contract.segments if s.purpose == "hook"]
        body_segments = [s for s in contract.segments if s.purpose == "body"]
        cta_segments = [s for s in contract.segments if s.purpose == "cta"]

        md_lines.extend(
            [
                "## Segment Summary",
                "",
                f"- **Hook Segments**: {len(hook_segments)} "
                f"({sum(s.est_duration_sec for s in hook_segments):.1f}s total)",
                f"- **Body Segments**: {len(body_segments)} "
                f"({sum(s.est_duration_sec for s in body_segments):.1f}s total)",
                f"- **CTA Segments**: {len(cta_segments)} "
                f"({sum(s.est_duration_sec for s in cta_segments):.1f}s total)",
                "",
                f"**Total Duration**: {total_duration:.1f}s (Target: {contract.target_duration_sec}s)",
                "",
            ]
        )

        # Quality notes
        duration_deviation = (
            (total_duration - contract.target_duration_sec)
            / contract.target_duration_sec
            * 100
        )

        md_lines.extend(
            [
                "## Quality Checks",
                "",
                f"✓ Hook segment present: {len(hook_segments) > 0}",
                f"✓ Body segment present: {len(body_segments) > 0}",
                f"✓ CTA segment present: {len(cta_segments) > 0}",
                f"✓ Duration within ±10%: {abs(duration_deviation) <= 10}",
                f"✓ No empty segments: {all(len(s.text.strip()) > 0 for s in contract.segments)}",
                "",
            ]
        )

        md_lines.extend(
            [
                "---",
                f"*Generated: {contract.created_at.isoformat()}*",
                f"*Script Contract ID: {contract.contract_id}*",
            ]
        )

        return "\n".join(md_lines)
