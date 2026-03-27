"""Upload provider abstraction for YouTube."""

from typing import Literal, Optional, Protocol

from pydantic import BaseModel

from app.domain.schemas import UploadRequest
from app.providers.base import CostEstimate, ProviderCallContext


class UploadResult(BaseModel):
    """Upload result."""

    video_id: str
    url: str
    status: str
    published_at: Optional[str] = None


class UploadStatus(BaseModel):
    """Upload status."""

    upload_id: str
    status: str
    bytes_confirmed: int
    video_id: Optional[str] = None


class ResumableUploadProbeResult(BaseModel):
    """Result of probing resumable upload session."""

    session_valid: bool
    status: Literal["ACTIVE", "COMPLETED", "EXPIRED", "FAILED"]
    bytes_confirmed_uploaded: int = 0
    video_id: Optional[str] = None


class UploadProvider(Protocol):
    """Upload provider protocol."""

    async def estimate_cost(
        self, req: UploadRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate upload cost."""
        ...

    async def upload(
        self, req: UploadRequest, ctx: ProviderCallContext
    ) -> UploadResult:
        """Upload video."""
        ...

    async def get_status(
        self, upload_id: str, ctx: ProviderCallContext
    ) -> UploadStatus:
        """Get upload status."""
        ...

    async def probe_resumable_session(
        self,
        session_uri: str,
        file_size_bytes: int,
        ctx: ProviderCallContext,
    ) -> ResumableUploadProbeResult:
        """Probe resumable upload session status."""
        ...

    async def resume_upload(
        self,
        session_uri: str,
        req: UploadRequest,
        offset_bytes: int,
        ctx: ProviderCallContext,
    ) -> UploadResult:
        """Resume upload from offset."""
        ...
