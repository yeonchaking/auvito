"""Asset generation provider abstraction."""

from typing import Optional, Protocol

from pydantic import BaseModel

from app.domain.schemas import ImageAssetRequest, VideoAssetRequest
from app.providers.base import CostEstimate, ProviderCallContext


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
