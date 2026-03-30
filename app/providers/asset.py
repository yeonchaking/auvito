"""Asset generation provider abstraction."""

import base64
import hashlib
import httpx
import io
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

from app.domain.schemas import ImageAssetRequest, VideoAssetRequest
from app.providers.base import CostEstimate, ProviderCallContext, ProviderMeta
from app.settings import load_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GeneratedAsset(BaseModel):
    """Generated asset."""

    asset_id: str
    uri: str
    sha256: str
    width: int
    height: int
    duration_sec: Optional[float] = None
    format: str
    meta: dict = {}


class AssetJobHandle(BaseModel):
    """Handle to async asset job."""

    job_id: str
    status: str
    created_at: str


class AssetJobStatus(BaseModel):
    """Status of async asset job."""

    job_id: str
    status: str
    progress_percent: Optional[int] = None
    error: Optional[str] = None


class AssetProvider(Protocol):
    """Asset provider protocol."""

    async def estimate_image_cost(
        self, req: ImageAssetRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate image generation cost."""
        ...

    async def generate_image(
        self, req: ImageAssetRequest, ctx: ProviderCallContext
    ) -> GeneratedAsset:
        """Generate image synchronously."""
        ...

    async def estimate_video_cost(
        self, req: VideoAssetRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate video generation cost."""
        ...

    async def submit_video(
        self, req: VideoAssetRequest, ctx: ProviderCallContext
    ) -> AssetJobHandle:
        """Submit video generation job."""
        ...

    async def get_video_status(
        self, job_id: str, ctx: ProviderCallContext
    ) -> AssetJobStatus:
        """Get video job status."""
        ...

    async def download_video(
        self, job_id: str, target_dir: str, ctx: ProviderCallContext
    ) -> GeneratedAsset:
        """Download completed video."""
        ...


class OpenAIAssetProvider:
    """OpenAI-based asset provider implementation."""

    API_BASE = "https://api.openai.com/v1"
    IMAGE_MODEL = "dall-e-3"
    VIDEO_MODEL = "sora-2"

    # Cost constants
    IMAGE_COST_USD = Decimal("0.04")  # dall-e-3 standard 1792x1024
    VIDEO_COST_USD_PER_SEC = Decimal("0.10")  # Estimated for Sora-2

    def __init__(self, api_key: Optional[str] = None, workspace_root: Optional[str] = None):
        """Initialize OpenAI asset provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            workspace_root: Workspace root for saving logs
        """
        settings, _ = load_settings()
        self.api_key = api_key or settings.openai_api_key
        self.workspace_root = workspace_root or settings.workspace_root

    async def estimate_image_cost(
        self, req: ImageAssetRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate image generation cost.

        High quality 1536x1024 images: ~$0.04 per image.

        Args:
            req: Image asset request
            ctx: Provider call context

        Returns:
            Cost estimate
        """
        return CostEstimate(
            estimated_cost_usd=self.IMAGE_COST_USD,
            confidence="high",
            reasoning="OpenAI GPT-Image-1 high quality 1536x1024 @ $0.04 per image",
        )

    async def generate_image(
        self, req: ImageAssetRequest, ctx: ProviderCallContext
    ) -> GeneratedAsset:
        """Generate image using OpenAI Images API.

        If no API key available, generates placeholder colored image using Pillow.

        Args:
            req: Image asset request
            ctx: Provider call context

        Returns:
            GeneratedAsset with URI and metadata

        Raises:
            ValueError: If generation fails
        """
        if not self.api_key:
            logger.info("No OPENAI_API_KEY provided, generating placeholder image")
            return self._generate_placeholder_image(req, ctx)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                request_body = {
                    "model": self.IMAGE_MODEL,
                    "prompt": req.prompt,
                    "size": "1792x1024",  # Landscape 16:9 (dall-e-3 supported size)
                    "quality": "standard",
                    "response_format": "b64_json",
                    "n": 1,
                }

                # Call OpenAI Images API
                response = await client.post(
                    f"{self.API_BASE}/images/generations",
                    json=request_body,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )

                if response.status_code != 200:
                    error_body = response.text
                    logger.error(
                        "OpenAI image API error",
                        status_code=response.status_code,
                        response_body=error_body,
                    )
                    # Parse error code for specific handling
                    try:
                        error_json = json.loads(error_body)
                        error_code = error_json.get("error", {}).get("code", "")
                        if error_code:
                            raise ValueError(f"OpenAI API error [{error_code}]: {error_body}")
                    except (json.JSONDecodeError, KeyError):
                        pass
                response.raise_for_status()
                response_data = response.json()

                # Extract base64 image data
                if not response_data.get("data") or not response_data["data"][0].get("b64_json"):
                    raise ValueError("No image data in response")

                image_b64 = response_data["data"][0]["b64_json"]
                image_bytes = base64.b64decode(image_b64)

                # Compute SHA256
                sha256_hash = hashlib.sha256(image_bytes).hexdigest()

                # Save image to file (use shot_id for unique filename per shot)
                shot_key = req.shot_id or f"{ctx.idempotency_key}_{ctx.stage_run_id}"
                asset_id = f"img_{hashlib.md5(shot_key.encode()).hexdigest()[:8]}"
                project_dir = ctx.project_slug or ctx.run_id
                workspace = Path(self.workspace_root) / "projects" / project_dir
                assets_dir = workspace / "05_assets" / "images"
                assets_dir.mkdir(parents=True, exist_ok=True)

                image_path = assets_dir / f"{asset_id}.png"
                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                logger.info(
                    "Image generated successfully",
                    asset_id=asset_id,
                    uri=str(image_path),
                    sha256=sha256_hash,
                )

                return GeneratedAsset(
                    asset_id=asset_id,
                    uri=str(image_path),
                    sha256=sha256_hash,
                    width=1536,
                    height=1024,
                    format="png",
                    meta={
                        "provider": "openai",
                        "model": self.IMAGE_MODEL,
                        "prompt": req.prompt,
                        "generated_at": datetime.utcnow().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(
                "Image generation failed",
                error=str(e),
                idempotency_key=ctx.idempotency_key,
            )
            raise ValueError(f"Image generation failed: {str(e)}") from e

    async def estimate_video_cost(
        self, req: VideoAssetRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate video generation cost.

        Sora-2 pricing estimate (Phase 2).

        Args:
            req: Video asset request
            ctx: Provider call context

        Returns:
            Cost estimate
        """
        estimated_cost = self.VIDEO_COST_USD_PER_SEC * Decimal(str(req.duration_sec))
        return CostEstimate(
            estimated_cost_usd=estimated_cost,
            confidence="low",
            reasoning=f"Sora-2 estimated @ $0.10/sec for {req.duration_sec}s (Phase 2)",
        )

    async def submit_video(
        self, req: VideoAssetRequest, ctx: ProviderCallContext
    ) -> AssetJobHandle:
        """Submit video generation job (Phase 2 - stub).

        Sora-2 video generation will be implemented in Phase 2.

        Args:
            req: Video asset request
            ctx: Provider call context

        Returns:
            AssetJobHandle

        Raises:
            NotImplementedError: Video generation not yet available
        """
        raise NotImplementedError(
            "Sora-2 video generation will be implemented in Phase 2. "
            "For now, fallback to static images with Ken Burns effect in Stage 6 (Render)."
        )

    async def get_video_status(
        self, job_id: str, ctx: ProviderCallContext
    ) -> AssetJobStatus:
        """Get video job status (Phase 2 - stub).

        Args:
            job_id: Video job ID
            ctx: Provider call context

        Returns:
            AssetJobStatus

        Raises:
            NotImplementedError: Video generation not yet available
        """
        raise NotImplementedError("Video generation not yet available (Phase 2)")

    async def download_video(
        self, job_id: str, target_dir: str, ctx: ProviderCallContext
    ) -> GeneratedAsset:
        """Download completed video (Phase 2 - stub).

        Args:
            job_id: Video job ID
            target_dir: Target directory for download
            ctx: Provider call context

        Returns:
            GeneratedAsset

        Raises:
            NotImplementedError: Video generation not yet available
        """
        raise NotImplementedError("Video generation not yet available (Phase 2)")

    def _generate_placeholder_image(
        self, req: ImageAssetRequest, ctx: ProviderCallContext
    ) -> GeneratedAsset:
        """Generate a placeholder colored image using Pillow.

        Args:
            req: Image asset request
            ctx: Provider call context

        Returns:
            GeneratedAsset with placeholder image

        Raises:
            ValueError: If image generation fails
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise ValueError(
                "Pillow is required for placeholder image generation. "
                "Install with: pip install Pillow"
            )

        # Create placeholder image with shot information
        width, height = req.width, req.height
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
        color_idx = hash(req.prompt) % len(colors)
        bg_color = colors[color_idx]

        # Convert hex color to RGB
        bg_color_rgb = tuple(int(bg_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

        image = Image.new("RGB", (width, height), bg_color_rgb)
        draw = ImageDraw.Draw(image)

        # Add text overlay
        text = "Placeholder Image"
        try:
            # Try to use a default font, fallback to default if not available
            font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # Draw text in center
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2

        draw.text((text_x, text_y), text, fill="white", font=font)

        # Save to bytes
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)
        image_data = image_bytes.getvalue()

        # Compute SHA256
        sha256_hash = hashlib.sha256(image_data).hexdigest()

        # Save to file
        asset_id = f"img_placeholder_{hashlib.md5(f'{ctx.idempotency_key}_{ctx.stage_run_id}'.encode()).hexdigest()[:8]}"
        workspace = Path(self.workspace_root) / "projects" / ctx.run_id
        assets_dir = workspace / "05_assets" / "images"
        assets_dir.mkdir(parents=True, exist_ok=True)

        image_path = assets_dir / f"{asset_id}.png"
        with open(image_path, "wb") as f:
            f.write(image_data)

        logger.info(
            "Placeholder image generated",
            asset_id=asset_id,
            uri=str(image_path),
            sha256=sha256_hash,
        )

        return GeneratedAsset(
            asset_id=asset_id,
            uri=str(image_path),
            sha256=sha256_hash,
            width=width,
            height=height,
            format="png",
            meta={
                "provider": "pillow",
                "model": "placeholder",
                "prompt": req.prompt,
                "generated_at": datetime.utcnow().isoformat(),
            },
        )
