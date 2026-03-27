"""Stage 8: YouTube upload (Phase 2)."""

from app.stages.base import BaseStage


class PublishStage(BaseStage):
    """Stage 8: YouTube upload (interface only in Phase 1)."""

    stage_name = "publish"

    async def execute(self, input_data) -> dict:
        """Upload to YouTube."""
        raise NotImplementedError("Upload stage is Phase 2")
