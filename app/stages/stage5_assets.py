"""Stage 5: Asset generation (images/videos)."""

import asyncio
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from app.domain.contracts import (
    AssetManifestAsset,
    AssetManifestContract,
    StoryboardContract,
)
from app.domain.models import AssetStageCheckpoint, AssetUnitState
from app.domain.schemas import ImageAssetRequest
from app.providers.asset import OpenAIAssetProvider
from app.providers.base import ProviderCallContext
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.storage.sqlite import Database
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Rate limit delay between image generation requests (free tier = 1 image/min).
# Set IMAGE_RATE_LIMIT_SEC=0 via environment to disable for paid-tier accounts.
import os as _os
IMAGE_RATE_LIMIT_SEC: float = float(_os.environ.get("IMAGE_RATE_LIMIT_SEC", "65"))


class AssetStageInput:
    """Input data for asset stage."""

    def __init__(
        self,
        storyboard_contract: StoryboardContract,
        workspace_root: str,
        openai_api_key: Optional[str] = None,
        stage_run_id: Optional[str] = None,
        max_concurrent: int = 1,
        project_slug: Optional[str] = None,
    ):
        """Initialize asset stage input.

        Args:
            storyboard_contract: StoryboardContract from Stage 4
            workspace_root: Workspace root directory
            openai_api_key: Optional OpenAI API key
            stage_run_id: Optional stage run ID
            max_concurrent: Maximum concurrent image generation tasks
            project_slug: Project slug for workspace path
        """
        self.storyboard_contract = storyboard_contract
        self.workspace_root = workspace_root
        self.openai_api_key = openai_api_key
        self.stage_run_id = stage_run_id
        self.max_concurrent = max_concurrent
        self.project_slug = project_slug


class AssetStage(BaseStage):
    """Stage 5: Asset generation with resumable checkpoint.

    Pipeline:
    1. Load storyboard contract and extract shots
    2. Initialize or load AssetStageCheckpoint
    3. For each shot, check checkpoint status:
       - COMPLETED → skip (reuse existing asset)
       - SUBMITTED + job_id → check video status (for future Sora-2)
       - PENDING/FAILED → generate new image
    4. Generate images concurrently with asyncio.Semaphore(5)
    5. Build AssetManifestContract from completed assets
    6. Save checkpoint after each unit completes

    Output:
    - asset_manifest.json (AssetManifestContract)
    - 05_assets/images/{shot_id}.png (generated images)
    - 05_assets/checkpoint.json (resumable checkpoint)
    """

    stage_name = "assets"

    def __init__(self, db: Database):
        """Initialize asset stage.

        Args:
            db: Database connection
        """
        self.db = db

    async def execute(self, input_data: AssetStageInput) -> AssetManifestContract:
        """Generate assets from storyboard.

        Creates:
        - asset_manifest.json (AssetManifestContract)
        - 05_assets/images/*.png (generated images)
        - 05_assets/checkpoint.json (resumable checkpoint)

        Args:
            input_data: Asset stage input

        Returns:
            AssetManifestContract

        Raises:
            ValueError: If asset generation fails
        """
        storyboard_contract = input_data.storyboard_contract
        project_slug = input_data.project_slug or storyboard_contract.run_id
        workspace = Path(input_data.workspace_root) / "projects" / project_slug
        assets_dir = workspace / "05_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Starting asset generation",
            storyboard_id=storyboard_contract.contract_id,
            shot_count=len(storyboard_contract.shots),
        )

        # Initialize provider
        asset_provider = OpenAIAssetProvider(
            api_key=input_data.openai_api_key,
            workspace_root=input_data.workspace_root,
        )

        # Load or initialize checkpoint
        checkpoint_path = assets_dir / "checkpoint.json"
        checkpoint = await self._load_or_init_checkpoint(
            checkpoint_path,
            storyboard_contract,
            input_data.stage_run_id or f"stg_{storyboard_contract.run_id}_assets_1",
        )

        # Create context for provider calls
        ctx = ProviderCallContext(
            run_id=storyboard_contract.run_id,
            stage_run_id=checkpoint.stage_run_id,
            attempt_no=1,
            idempotency_key=self._compute_idempotency_key(
                storyboard_contract.contract_id
            ),
            project_slug=project_slug,
        )

        try:
            # Generate assets concurrently
            semaphore = asyncio.Semaphore(input_data.max_concurrent)
            tasks = []

            all_shots = storyboard_contract.shots
            for idx, shot in enumerate(all_shots):
                unit_id = shot.shot_id
                task = self._process_shot(
                    shot,
                    asset_provider,
                    checkpoint,
                    checkpoint_path,
                    ctx,
                    semaphore,
                    storyboard_contract.aspect_ratio,
                    is_last=(idx == len(all_shots) - 1),
                )
                tasks.append(task)

            # Execute all generation tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            generated_assets = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(
                        "Asset generation task failed",
                        error=str(result),
                    )
                    # Continue with next shot
                    continue
                if result is not None:
                    generated_assets.append(result)

            # Validate that all shots have assets
            if len(generated_assets) != len(storyboard_contract.shots):
                logger.warning(
                    "Not all shots have assets",
                    generated_count=len(generated_assets),
                    shot_count=len(storyboard_contract.shots),
                )

            # Create AssetManifestContract
            manifest_contract = self._create_asset_manifest(
                generated_assets,
                storyboard_contract,
                ctx,
            )

            # Save manifest
            manifest_path = assets_dir / "asset_manifest.json"
            await FileStorage.save_json(
                str(manifest_path),
                json.loads(manifest_contract.model_dump_json()),
            )

            logger.info(
                "Asset generation completed",
                storyboard_id=storyboard_contract.contract_id,
                manifest_id=manifest_contract.contract_id,
                asset_count=len(generated_assets),
            )

            return manifest_contract

        except Exception as e:
            logger.error(
                "Asset generation failed",
                storyboard_id=storyboard_contract.contract_id,
                error=str(e),
            )
            raise ValueError(f"Asset generation failed: {str(e)}") from e

    async def _load_or_init_checkpoint(
        self,
        checkpoint_path: Path,
        storyboard_contract: StoryboardContract,
        stage_run_id: str,
    ) -> AssetStageCheckpoint:
        """Load existing checkpoint or initialize new one.

        Args:
            checkpoint_path: Path to checkpoint file
            storyboard_contract: Storyboard contract
            stage_run_id: Stage run ID

        Returns:
            AssetStageCheckpoint
        """
        if await FileStorage.file_exists(str(checkpoint_path)):
            checkpoint_data = await FileStorage.load_json(str(checkpoint_path))
            if checkpoint_data:
                try:
                    return AssetStageCheckpoint(**checkpoint_data)
                except Exception as e:
                    logger.warning(
                        "Failed to load checkpoint, creating new one",
                        error=str(e),
                    )

        # Initialize new checkpoint
        units = {}
        for shot in storyboard_contract.shots:
            request_digest = hashlib.sha256(
                f"{shot.shot_id}:{shot.prompt}:{shot.visual_kind}".encode()
            ).hexdigest()

            units[shot.shot_id] = AssetUnitState(
                unit_id=shot.shot_id,
                kind=shot.visual_kind,
                status="PENDING",
                request_digest=request_digest,
            )

        checkpoint = AssetStageCheckpoint(
            checkpoint_version="1.0",
            stage_run_id=stage_run_id,
            units=units,
        )

        logger.info(
            "Initialized new checkpoint",
            stage_run_id=stage_run_id,
            unit_count=len(units),
        )

        return checkpoint

    async def _save_checkpoint(
        self, checkpoint: AssetStageCheckpoint, checkpoint_path: Path
    ) -> None:
        """Save checkpoint to file.

        Args:
            checkpoint: AssetStageCheckpoint
            checkpoint_path: Path to save checkpoint
        """
        await FileStorage.save_json(
            str(checkpoint_path),
            json.loads(checkpoint.model_dump_json()),
        )

    async def _process_shot(
        self,
        shot,
        asset_provider,
        checkpoint: AssetStageCheckpoint,
        checkpoint_path: Path,
        ctx: ProviderCallContext,
        semaphore: asyncio.Semaphore,
        aspect_ratio: str,
        is_last: bool = False,
    ):
        """Process a single shot and generate asset.

        Args:
            shot: StoryboardShot
            asset_provider: Asset provider instance
            checkpoint: Current checkpoint
            checkpoint_path: Path to checkpoint file
            ctx: Provider call context
            semaphore: Concurrency semaphore
            aspect_ratio: Target aspect ratio

        Returns:
            AssetManifestAsset or None
        """
        unit_id = shot.shot_id
        unit_state = checkpoint.units.get(unit_id)

        if not unit_state:
            logger.error("Unit state not found in checkpoint", unit_id=unit_id)
            return None

        # Check if already completed
        if unit_state.status == "COMPLETED" and unit_state.asset_uri:
            logger.info("Reusing existing asset", unit_id=unit_id, uri=unit_state.asset_uri)
            return AssetManifestAsset(
                asset_id=unit_id,
                shot_id=unit_id,
                kind=unit_state.kind,
                source_type="generated",
                uri=unit_state.asset_uri,
                width=1536 if aspect_ratio == "16:9" else 1024,
                height=1024 if aspect_ratio == "16:9" else 1536,
                duration_sec=shot.end_sec - shot.start_sec if shot.visual_kind == "video" else None,
            )

        # For now, only support image generation (video is Phase 2)
        if shot.visual_kind == "video":
            logger.warning(
                "Video generation not yet supported, skipping",
                shot_id=unit_id,
            )
            return None

        # Generate image
        async with semaphore:
            try:
                logger.info("Generating image", shot_id=unit_id, prompt=shot.prompt[:100])

                # Create image request
                image_req = ImageAssetRequest(
                    prompt=shot.prompt,
                    width=1536,
                    height=1024,
                    shot_id=unit_id,
                )

                # Generate image (rate limit: wait 65s between requests for free tier)
                try:
                    generated_asset = await asset_provider.generate_image(image_req, ctx)
                except ValueError as img_err:
                    if "content_policy_violation" in str(img_err):
                        # Retry with a softer, abstract prompt
                        logger.warning(
                            "Content policy violation, retrying with abstract prompt",
                            shot_id=unit_id,
                        )
                        if IMAGE_RATE_LIMIT_SEC > 0:
                            await asyncio.sleep(IMAGE_RATE_LIMIT_SEC)
                        safe_prompt = (
                            f"Abstract historical Korean illustration, symbolic artistic composition, "
                            f"muted earth tones, traditional ink painting style, documentary aesthetic, "
                            f"no people, no violence, conceptual representation of ancient Korean history"
                        )
                        safe_req = ImageAssetRequest(
                            prompt=safe_prompt,
                            width=image_req.width,
                            height=image_req.height,
                            shot_id=unit_id,
                        )
                        generated_asset = await asset_provider.generate_image(safe_req, ctx)
                    else:
                        raise
                # Rate limit: skip sleep on last shot to save time
                if IMAGE_RATE_LIMIT_SEC > 0 and not is_last:
                    logger.debug(
                        "Rate limit wait",
                        delay_sec=IMAGE_RATE_LIMIT_SEC,
                        shot_id=unit_id,
                    )
                    await asyncio.sleep(IMAGE_RATE_LIMIT_SEC)

                # Update checkpoint
                unit_state.status = "COMPLETED"
                unit_state.asset_uri = generated_asset.uri
                unit_state.asset_sha256 = generated_asset.sha256
                unit_state.actual_cost_usd = asset_provider.IMAGE_COST_USD

                # Save checkpoint
                await self._save_checkpoint(checkpoint, checkpoint_path)

                logger.info(
                    "Asset generated",
                    unit_id=unit_id,
                    uri=generated_asset.uri,
                    sha256=generated_asset.sha256,
                )

                return AssetManifestAsset(
                    asset_id=generated_asset.asset_id,
                    shot_id=unit_id,
                    kind="image",
                    source_type="generated",
                    uri=generated_asset.uri,
                    width=generated_asset.width,
                    height=generated_asset.height,
                    duration_sec=None,
                )

            except Exception as e:
                logger.error(
                    "Asset generation error",
                    shot_id=unit_id,
                    error=str(e),
                )
                unit_state.status = "FAILED"
                unit_state.last_error = str(e)
                unit_state.retry_count += 1

                # Save checkpoint
                await self._save_checkpoint(checkpoint, checkpoint_path)

                return None

    def _create_asset_manifest(
        self,
        generated_assets: list[AssetManifestAsset],
        storyboard_contract: StoryboardContract,
        ctx: ProviderCallContext,
    ) -> AssetManifestContract:
        """Create AssetManifestContract from generated assets.

        Args:
            generated_assets: List of generated assets
            storyboard_contract: Storyboard contract
            ctx: Provider call context

        Returns:
            AssetManifestContract
        """
        manifest_id = f"am_{hashlib.md5(f'{ctx.run_id}{ctx.stage_run_id}'.encode()).hexdigest()[:8]}"

        manifest = AssetManifestContract(
            contract_type="asset_manifest",
            schema_version="1.0",
            contract_id=manifest_id,
            run_id=ctx.run_id,
            generated_by_stage_run_id=ctx.stage_run_id,
            created_at=datetime.utcnow(),
            storyboard_id=storyboard_contract.contract_id,
            selected_assets=generated_assets,
        )

        return manifest

    def _compute_idempotency_key(self, storyboard_id: str) -> str:
        """Compute idempotency key for asset generation.

        Args:
            storyboard_id: Storyboard contract ID

        Returns:
            Idempotency key hash
        """
        content = f"{storyboard_id}:assets_v1"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
