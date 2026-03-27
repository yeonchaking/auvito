"""Stage 7: Thumbnail generation (Phase 2)."""

from app.stages.base import BaseStage


class ThumbnailStage(BaseStage):
    """Stage 7: Thumbnail generation (interface only in Phase 1)."""

    stage_name = "thumbnail"

    async def execute(self, input_data) -> dict:
        """Generate thumbnail."""
        raise NotImplementedError("Thumbnail stage is Phase 2")
