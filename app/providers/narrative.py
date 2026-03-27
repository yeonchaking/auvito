"""Narrative provider abstraction for LLM-based text generation."""

from typing import Any, Optional, Protocol

from pydantic import BaseModel

from app.domain.contracts import (
    ScriptContract,
    StoryboardContract,
    UploadMetadataContract,
)
from app.domain.schemas import (
    MetadataRequest,
    ScriptRequest,
    StoryboardRequest,
)
from app.providers.base import CostEstimate, ProviderCallContext


class ThumbnailCopyResult(BaseModel):
    """Thumbnail copy generation result."""

    headline: str
    subheading: Optional[str] = None
    cta_text: Optional[str] = None


class ThumbnailCopyRequest(BaseModel):
    """Thumbnail copy generation request."""

    project_title: str
    benchmark_report_path: Optional[str] = None
    ctr_patterns: Optional[dict[str, Any]] = None


class NarrativeProvider(Protocol):
    """Narrative provider protocol for text generation."""

    async def estimate_script_cost(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate script generation cost."""
        ...

    async def generate_script(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> ScriptContract:
        """Generate script."""
        ...

    async def estimate_storyboard_cost(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate storyboard generation cost."""
        ...

    async def generate_storyboard(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> StoryboardContract:
        """Generate storyboard."""
        ...

    async def estimate_thumbnail_copy_cost(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate thumbnail copy generation cost."""
        ...

    async def generate_thumbnail_copy(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> ThumbnailCopyResult:
        """Generate thumbnail copy."""
        ...

    async def estimate_metadata_cost(
        self, req: MetadataRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate metadata generation cost."""
        ...

    async def generate_metadata(
        self, req: MetadataRequest, ctx: ProviderCallContext
    ) -> UploadMetadataContract:
        """Generate upload metadata."""
        ...
