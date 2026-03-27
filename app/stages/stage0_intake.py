"""Stage 0: Project intake and setup."""

from app.stages.base import BaseStage


class IntakeStage(BaseStage):
    """Stage 0: Project creation and setup."""

    stage_name = "intake"

    async def execute(self, input_data) -> dict:
        """Create project directory structure."""
        return {"status": "intake_created"}
