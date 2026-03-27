"""Stage 6: Video rendering."""

from app.stages.base import BaseStage


class RenderStage(BaseStage):
    """Stage 6: FFmpeg rendering to draft.mp4."""

    stage_name = "render"

    async def execute(self, input_data) -> dict:
        """Render video."""
        return {"status": "render_complete"}
