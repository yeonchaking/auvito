"""Stage 6: Video rendering."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.contracts import (
    AssetManifestContract,
    NarrationContract,
    RenderNarrationTrack,
    RenderOutput,
    RenderPlanContract,
    RenderSubtitles,
    RenderTimelineItem,
    StoryboardContract,
)
from app.services.ffmpeg_service import FFmpegService
from app.services.pillow_service import PillowService
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RenderStageInput:
    """Input data for render stage."""

    def __init__(
        self,
        narration_contract: NarrationContract,
        storyboard_contract: StoryboardContract,
        asset_manifest_contract: AssetManifestContract,
        workspace_root: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        video_codec: str = "h264",
        audio_codec: str = "aac",
        font_path: Optional[str] = None,
        stage_run_id: Optional[str] = None,
        project_slug: Optional[str] = None,
    ):
        """Initialize render stage input.

        Args:
            narration_contract: NarrationContract from Stage 3
            storyboard_contract: StoryboardContract from Stage 4
            asset_manifest_contract: AssetManifestContract from Stage 5
            workspace_root: Workspace root directory
            width: Output video width
            height: Output video height
            fps: Frames per second
            video_codec: Video codec (h264, h265, etc.)
            audio_codec: Audio codec (aac, mp3, etc.)
            font_path: Path to font file for subtitles
            stage_run_id: Optional stage run ID
            project_slug: Project slug for workspace path
        """
        self.narration_contract = narration_contract
        self.storyboard_contract = storyboard_contract
        self.asset_manifest_contract = asset_manifest_contract
        self.workspace_root = workspace_root
        self.width = width
        self.height = height
        self.fps = fps
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.font_path = font_path
        self.stage_run_id = stage_run_id
        self.project_slug = project_slug


class RenderStage(BaseStage):
    """Stage 6: FFmpeg rendering to draft.mp4.

    Processing pipeline:
    1. Load all three input contracts (narration, storyboard, assets)
    2. Build timeline: for each shot, match asset from manifest
    3. For each timeline item: create video clip from image (with motion preset)
    4. Concatenate all clips in order
    5. Overlay narration audio
    6. Burn subtitles from NarrationContract
    7. Encode final: draft.mp4 (1920x1080, 30fps, h264+aac)

    Output: RenderPlanContract + draft.mp4
    """

    stage_name = "render"

    def __init__(self):
        """Initialize render stage."""
        self.ffmpeg_service = FFmpegService()
        self.pillow_service = PillowService()

    async def execute(self, input_data: RenderStageInput) -> RenderPlanContract:
        """Render video from contracts and assets.

        Creates:
        - render_plan.json (RenderPlanContract)
        - draft.mp4 (encoded video with audio and burned subtitles)

        Args:
            input_data: RenderStageInput

        Returns:
            RenderPlanContract

        Raises:
            ValueError: If rendering fails
        """
        narration_contract = input_data.narration_contract
        storyboard_contract = input_data.storyboard_contract
        asset_manifest_contract = input_data.asset_manifest_contract

        project_slug = input_data.project_slug or storyboard_contract.run_id
        workspace = (
            Path(input_data.workspace_root)
            / "projects"
            / project_slug
        )
        render_dir = workspace / "06_render"
        await FileStorage.ensure_dir(str(render_dir))

        logger.info(
            "Starting render stage",
            narration_id=narration_contract.contract_id,
            storyboard_id=storyboard_contract.contract_id,
            asset_count=len(asset_manifest_contract.selected_assets),
            shot_count=len(storyboard_contract.shots),
        )

        try:
            timeline_items = self._build_timeline(
                storyboard_contract, asset_manifest_contract
            )

            if not timeline_items:
                raise ValueError("Failed to build timeline")

            logger.info(
                "Timeline built",
                item_count=len(timeline_items),
            )

            draft_output = str(render_dir / "draft.mp4")

            image_paths = []
            durations = []
            motion_presets = []

            for item in timeline_items:
                asset = self._find_asset(item.asset_id, asset_manifest_contract)
                if not asset:
                    logger.warning(
                        "Asset not found, using black frame",
                        asset_id=item.asset_id,
                    )
                    black_frame_path = str(
                        render_dir / f"black_frame_{item.item_id}.png"
                    )
                    if not await self._create_black_frame(black_frame_path):
                        raise ValueError(
                            f"Failed to create black frame for item {item.item_id}"
                        )
                    image_paths.append(black_frame_path)
                else:
                    image_paths.append(asset.uri)

                durations.append(item.end_sec - item.start_sec)
                motion_presets.append(item.motion_preset)

            logger.info(
                "Creating draft video",
                image_count=len(image_paths),
                narration_audio=narration_contract.narration_audio_uri,
                subtitles=narration_contract.subtitles_uri,
            )

            success = await self.ffmpeg_service.create_draft(
                image_paths=image_paths,
                durations=durations,
                motion_presets=motion_presets,
                narration_audio_path=narration_contract.narration_audio_uri,
                subtitles_path=narration_contract.subtitles_uri,
                output_path=draft_output,
                width=input_data.width,
                height=input_data.height,
                fps=input_data.fps,
                font_path=input_data.font_path,
            )

            if not success:
                raise ValueError("FFmpeg draft creation failed")

            logger.info(
                "Draft video created",
                output=draft_output,
            )

            final_duration = await self.ffmpeg_service.get_duration(draft_output)
            if final_duration is None:
                logger.warning("Could not determine final duration, using narration duration")
                final_duration = narration_contract.total_duration_sec

            render_plan = self._create_render_plan(
                narration_contract,
                storyboard_contract,
                asset_manifest_contract,
                timeline_items,
                draft_output,
                final_duration,
                input_data.width,
                input_data.height,
                input_data.fps,
                input_data.video_codec,
                input_data.audio_codec,
                input_data.stage_run_id,
                storyboard_contract.run_id,
            )

            render_plan_path = str(render_dir / "render_plan.json")
            await FileStorage.save_json(
                render_plan_path,
                json.loads(render_plan.model_dump_json()),
            )

            logger.info(
                "Render stage completed",
                render_plan_id=render_plan.contract_id,
                final_duration=final_duration,
                output_uri=draft_output,
            )

            return render_plan

        except Exception as e:
            logger.error(
                "Render stage failed",
                narration_id=narration_contract.contract_id,
                error=str(e),
            )
            raise ValueError(f"Render stage failed: {str(e)}") from e

    def _build_timeline(
        self,
        storyboard_contract: StoryboardContract,
        asset_manifest_contract: AssetManifestContract,
    ) -> list[RenderTimelineItem]:
        """Build timeline from storyboard shots with motion presets.

        Args:
            storyboard_contract: StoryboardContract
            asset_manifest_contract: AssetManifestContract

        Returns:
            List of RenderTimelineItem objects
        """
        timeline = []

        for shot in storyboard_contract.shots:
            asset = None
            for ast in asset_manifest_contract.selected_assets:
                if ast.shot_id == shot.shot_id:
                    asset = ast
                    break

            if not asset:
                logger.warning(
                    "No asset found for shot",
                    shot_id=shot.shot_id,
                )
                continue

            motion_preset = shot.motion_hint or "static"

            item = RenderTimelineItem(
                item_id=f"itm_{hashlib.md5(shot.shot_id.encode()).hexdigest()[:8]}",
                shot_id=shot.shot_id,
                asset_id=asset.asset_id,
                start_sec=shot.start_sec,
                end_sec=shot.end_sec,
                motion_preset=motion_preset,
            )

            timeline.append(item)

        logger.info(
            "Timeline built",
            shot_count=len(storyboard_contract.shots),
            item_count=len(timeline),
        )

        return timeline

    def _find_asset(self, asset_id: str, manifest: AssetManifestContract):
        """Find asset by ID in manifest.

        Args:
            asset_id: Asset ID to find
            manifest: AssetManifestContract

        Returns:
            AssetManifestAsset or None
        """
        for asset in manifest.selected_assets:
            if asset.asset_id == asset_id:
                return asset
        return None

    async def _create_black_frame(self, output_path: str) -> bool:
        """Create a black 1920x1080 image for missing assets.

        Args:
            output_path: Path to save black frame

        Returns:
            True if successful, False otherwise
        """
        try:
            from PIL import Image

            img = Image.new("RGB", (1920, 1080), color=(0, 0, 0))
            img.save(output_path)
            return True
        except Exception as e:
            logger.error(
                "Black frame creation failed",
                output=output_path,
                error=str(e),
            )
            return False

    def _create_render_plan(
        self,
        narration_contract: NarrationContract,
        storyboard_contract: StoryboardContract,
        asset_manifest_contract: AssetManifestContract,
        timeline_items: list[RenderTimelineItem],
        draft_output_uri: str,
        final_duration: float,
        width: int,
        height: int,
        fps: int,
        video_codec: str,
        audio_codec: str,
        stage_run_id: Optional[str],
        run_id: str,
    ) -> RenderPlanContract:
        """Create RenderPlanContract from rendering results.

        Args:
            narration_contract: NarrationContract
            storyboard_contract: StoryboardContract
            asset_manifest_contract: AssetManifestContract
            timeline_items: List of timeline items
            draft_output_uri: Path to draft.mp4
            final_duration: Total duration of rendered video
            width: Output width
            height: Output height
            fps: Frames per second
            video_codec: Video codec
            audio_codec: Audio codec
            stage_run_id: Stage run ID
            run_id: Run ID

        Returns:
            RenderPlanContract
        """
        render_plan_id = f"rp_{hashlib.md5(f'{run_id}{datetime.utcnow().isoformat()}'.encode()).hexdigest()[:8]}"

        aspect_ratio = f"{width}:{height}"
        if width == 1920 and height == 1080:
            aspect_ratio = "16:9"
        elif width == 1080 and height == 1920:
            aspect_ratio = "9:16"

        output = RenderOutput(
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
            fps=fps,
            video_codec=video_codec,
            audio_codec=audio_codec,
            draft_output_uri=draft_output_uri,
            final_output_uri=draft_output_uri.replace("draft.mp4", "final.mp4"),
            final_duration_sec=final_duration,
        )

        narration_track = RenderNarrationTrack(
            uri=narration_contract.narration_audio_uri,
        )

        subtitles = RenderSubtitles(
            uri=narration_contract.subtitles_uri,
            burn_in=True,
        )

        render_plan = RenderPlanContract(
            contract_id=render_plan_id,
            run_id=run_id,
            generated_by_stage_run_id=stage_run_id
            or f"stg_{run_id}_render_1",
            created_at=datetime.utcnow(),
            storyboard_id=storyboard_contract.contract_id,
            asset_manifest_id=asset_manifest_contract.contract_id,
            output=output,
            narration_track=narration_track,
            timeline_items=timeline_items,
            subtitles=subtitles,
        )

        return render_plan
