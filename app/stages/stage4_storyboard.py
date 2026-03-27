"""Stage 4: Storyboard generation."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.contracts import (
    NarrationContract,
    ScriptContract,
    StoryboardContract,
    StoryboardShot,
)
from app.domain.schemas import StoryboardRequest
from app.providers.narrative import AnthropicNarrativeProvider
from app.providers.base import ProviderCallContext
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.storage.sqlite import Database
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StoryboardStageInput:
    """Input data for storyboard stage."""

    def __init__(
        self,
        script_contract: ScriptContract,
        narration_contract: NarrationContract,
        workspace_root: str,
        anthropic_api_key: Optional[str] = None,
        aspect_ratio: str = "16:9",
    ):
        """Initialize storyboard stage input.

        Args:
            script_contract: ScriptContract from Stage 2
            narration_contract: NarrationContract from Stage 3
            workspace_root: Workspace root directory
            anthropic_api_key: Optional Anthropic API key
            aspect_ratio: Target aspect ratio (default: 16:9)
        """
        self.script_contract = script_contract
        self.narration_contract = narration_contract
        self.workspace_root = workspace_root
        self.anthropic_api_key = anthropic_api_key
        self.aspect_ratio = aspect_ratio


class StoryboardStage(BaseStage):
    """Stage 4: Storyboard generation with visual shot planning.

    Pipeline:
    1. Load script and narration contracts
    2. Build scene context from script segments + narration clip timings
    3. Call LLM (via NarrativeProvider.generate_storyboard) to create visual shot list
    4. Validate and adjust shot timings to match NarrationContract exactly
    5. Generate detailed image/video prompts for each shot

    Output:
    - storyboard_contract.json (StoryboardContract)
    - visual_style_guide.md (human-readable style guide)
    - image_prompts.jsonl (one shot per line with prompt)
    """

    stage_name = "storyboard"

    def __init__(self, db: Database):
        """Initialize storyboard stage.

        Args:
            db: Database connection
        """
        self.db = db

    async def execute(self, input_data: StoryboardStageInput) -> StoryboardContract:
        """Generate storyboard with visual shot planning.

        Creates:
        - storyboard_contract.json (StoryboardContract)
        - visual_style_guide.md (human-readable)
        - image_prompts.jsonl (one JSON per line)

        Args:
            input_data: Storyboard stage input

        Returns:
            StoryboardContract

        Raises:
            ValueError: If storyboard generation fails
        """
        script_contract = input_data.script_contract
        narration_contract = input_data.narration_contract
        workspace = Path(input_data.workspace_root) / "projects" / script_contract.run_id
        storyboard_dir = workspace / "04_storyboard"
        storyboard_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Starting storyboard generation",
            script_id=script_contract.contract_id,
            narration_id=narration_contract.contract_id,
            total_duration=narration_contract.total_duration_sec,
        )

        # Create provider
        narrative_provider = AnthropicNarrativeProvider(
            api_key=input_data.anthropic_api_key,
            workspace_root=input_data.workspace_root,
        )

        # Create storyboard request
        storyboard_request = StoryboardRequest(
            script_path=str(workspace / "02_script" / "script_contract.json"),
            narration_path=str(
                workspace / "03_voice" / "narration_contract.json"
            ),
            niche=script_contract.run_id,  # Use run_id as niche placeholder
        )

        # Create provider context
        ctx = ProviderCallContext(
            run_id=script_contract.run_id,
            stage_run_id=f"stg_{script_contract.run_id}_{self.stage_name}_1",
            attempt_no=1,
            idempotency_key=self._compute_idempotency_key(
                script_contract.contract_id, narration_contract.contract_id
            ),
        )

        try:
            # Estimate cost
            cost_estimate = await narrative_provider.estimate_storyboard_cost(
                storyboard_request, ctx
            )
            logger.info(
                "Storyboard generation cost estimated",
                estimated_cost=cost_estimate.estimated_cost_usd,
            )

            # Generate storyboard
            storyboard_contract = await narrative_provider.generate_storyboard(
                storyboard_request,
                ctx,
                script_contract=script_contract,
                narration_contract=narration_contract,
                aspect_ratio=input_data.aspect_ratio,
            )

            # Validate shot coverage (no gaps, no overlaps, 100% duration)
            self._validate_shot_coverage(
                storyboard_contract.shots, narration_contract.total_duration_sec
            )

            # Save storyboard contract as JSON
            contract_json_path = storyboard_dir / "storyboard_contract.json"
            await FileStorage.save_json(
                str(contract_json_path),
                json.loads(storyboard_contract.model_dump_json()),
            )

            # Generate and save visual style guide markdown
            visual_style_guide = self._generate_visual_style_guide(
                storyboard_contract, script_contract
            )
            visual_style_path = storyboard_dir / "visual_style_guide.md"
            await FileStorage.save_text(str(visual_style_path), visual_style_guide)

            # Generate and save image prompts JSONL
            image_prompts_path = storyboard_dir / "image_prompts.jsonl"
            await self._save_image_prompts_jsonl(
                storyboard_contract, str(image_prompts_path)
            )

            logger.info(
                "Storyboard generation completed",
                script_id=script_contract.contract_id,
                storyboard_id=storyboard_contract.contract_id,
                shot_count=len(storyboard_contract.shots),
                total_duration=storyboard_contract.total_duration_sec,
            )

            return storyboard_contract

        except Exception as e:
            logger.error(
                "Storyboard generation failed",
                script_id=script_contract.contract_id,
                error=str(e),
            )
            raise ValueError(f"Storyboard generation failed: {str(e)}") from e

    def _compute_idempotency_key(self, script_id: str, narration_id: str) -> str:
        """Compute idempotency key for storyboard execution.

        Args:
            script_id: Script contract ID
            narration_id: Narration contract ID

        Returns:
            Idempotency key hash
        """
        content = f"{script_id}:{narration_id}:storyboard_v1"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _validate_shot_coverage(self, shots: list[StoryboardShot], total_duration_sec: float) -> None:
        """Validate that shots cover 100% of duration with no gaps or overlaps.

        Args:
            shots: List of StoryboardShot objects
            total_duration_sec: Total video duration in seconds

        Raises:
            ValueError: If validation fails
        """
        if not shots:
            raise ValueError("No shots defined in storyboard")

        # Sort shots by start time
        sorted_shots = sorted(shots, key=lambda s: s.start_sec)

        # Check for gaps and overlaps
        epsilon = 0.1  # Allow small timing differences (100ms)
        for i, shot in enumerate(sorted_shots):
            # Check ordering
            if shot.order != i + 1:
                logger.warning(
                    f"Shot {shot.shot_id} has order {shot.order}, expected {i + 1}. Auto-correcting.",
                    shot_id=shot.shot_id,
                )

            # Check that start < end
            if shot.start_sec >= shot.end_sec:
                raise ValueError(
                    f"Shot {shot.shot_id} has invalid timing: "
                    f"start={shot.start_sec}, end={shot.end_sec}"
                )

            # Check for gap or overlap with next shot
            if i < len(sorted_shots) - 1:
                next_shot = sorted_shots[i + 1]
                gap = next_shot.start_sec - shot.end_sec

                if gap > epsilon:
                    raise ValueError(
                        f"Gap detected between {shot.shot_id} and {next_shot.shot_id}: "
                        f"{gap:.2f}s gap at {shot.end_sec}s"
                    )
                elif gap < -epsilon:
                    raise ValueError(
                        f"Overlap detected between {shot.shot_id} and {next_shot.shot_id}: "
                        f"{-gap:.2f}s overlap at {shot.end_sec}s"
                    )

        # Check start and end times
        first_shot = sorted_shots[0]
        last_shot = sorted_shots[-1]

        if first_shot.start_sec > epsilon:
            raise ValueError(
                f"First shot {first_shot.shot_id} does not start at 0.0s, "
                f"starts at {first_shot.start_sec}s"
            )

        if abs(last_shot.end_sec - total_duration_sec) > epsilon:
            raise ValueError(
                f"Last shot {last_shot.shot_id} does not end at {total_duration_sec}s, "
                f"ends at {last_shot.end_sec}s"
            )

        logger.info(
            "Shot coverage validation passed",
            shot_count=len(shots),
            total_duration=total_duration_sec,
        )

    def _generate_visual_style_guide(
        self, storyboard_contract: StoryboardContract, script_contract: ScriptContract
    ) -> str:
        """Generate human-readable visual style guide markdown.

        Args:
            storyboard_contract: StoryboardContract
            script_contract: ScriptContract for context

        Returns:
            Markdown formatted style guide
        """
        md_lines = [
            "# Visual Style Guide",
            "",
            f"**Project**: {script_contract.title}",
            f"**Duration**: {storyboard_contract.total_duration_sec} seconds",
            f"**Aspect Ratio**: {storyboard_contract.aspect_ratio}",
            f"**Generated**: {storyboard_contract.created_at.isoformat()}",
            "",
            "---",
            "",
            "## Style Parameters",
            "",
            "- **Tone**: Professional and trustworthy",
            "- **Color Palette**: Bright and modern",
            "- **Composition**: Balanced and focused",
            "- **Motion**: Subtle and purposeful",
            "",
            "---",
            "",
            "## Shot Breakdown",
            "",
        ]

        # Group shots by content type
        image_shots = [s for s in storyboard_contract.shots if s.visual_kind == "image"]
        video_shots = [s for s in storyboard_contract.shots if s.visual_kind == "video"]

        md_lines.extend(
            [
                f"### Summary",
                f"- **Total Shots**: {len(storyboard_contract.shots)}",
                f"- **Image Shots**: {len(image_shots)}",
                f"- **Video Shots**: {len(video_shots)}",
                "",
                "---",
                "",
            ]
        )

        # Detailed shot list
        md_lines.append("### Detailed Shot List")
        md_lines.append("")

        for shot in storyboard_contract.shots:
            duration = shot.end_sec - shot.start_sec
            shot_type = shot.visual_kind.upper()

            md_lines.extend(
                [
                    f"#### Shot {shot.order}: {shot.shot_id}",
                    f"**Type**: {shot_type} | **Duration**: {duration:.1f}s",
                    f"**Time**: {shot.start_sec:.1f}s → {shot.end_sec:.1f}s",
                    f"**Motion**: {shot.motion_hint or 'static'}",
                    f"**Linked Narration**: {', '.join(shot.narration_clip_ids)}",
                    "",
                    f"**Prompt**:",
                    "",
                    f"> {shot.prompt}",
                    "",
                ]
            )

        # Summary statistics
        total_image_duration = sum(
            s.end_sec - s.start_sec
            for s in storyboard_contract.shots
            if s.visual_kind == "image"
        )
        total_video_duration = sum(
            s.end_sec - s.start_sec
            for s in storyboard_contract.shots
            if s.visual_kind == "video"
        )

        md_lines.extend(
            [
                "---",
                "",
                "## Coverage Summary",
                "",
                f"- **Image Coverage**: {total_image_duration:.1f}s ({total_image_duration/storyboard_contract.total_duration_sec*100:.1f}%)",
                f"- **Video Coverage**: {total_video_duration:.1f}s ({total_video_duration/storyboard_contract.total_duration_sec*100:.1f}%)",
                "",
                "---",
                "",
                f"*Generated by Stage 4 (Storyboard) - Storyboard ID: {storyboard_contract.contract_id}*",
            ]
        )

        return "\n".join(md_lines)

    async def _save_image_prompts_jsonl(
        self, storyboard_contract: StoryboardContract, output_path: str
    ) -> None:
        """Save image prompts as JSONL (one JSON object per line).

        Args:
            storyboard_contract: StoryboardContract with shots
            output_path: Path to save JSONL file
        """
        lines = []
        for shot in storyboard_contract.shots:
            prompt_obj = {
                "shot_id": shot.shot_id,
                "order": shot.order,
                "visual_kind": shot.visual_kind,
                "prompt": shot.prompt,
                "start_sec": shot.start_sec,
                "end_sec": shot.end_sec,
                "duration_sec": shot.end_sec - shot.start_sec,
            }
            lines.append(json.dumps(prompt_obj, ensure_ascii=False))

        await FileStorage.save_text(output_path, "\n".join(lines))
        logger.info(
            "Image prompts saved",
            output_path=output_path,
            prompt_count=len(lines),
        )
