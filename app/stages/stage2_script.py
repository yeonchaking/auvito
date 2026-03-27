"""Stage 2: Script generation."""

from app.stages.base import BaseStage


class ScriptStage(BaseStage):
    """Stage 2: Script generation."""

    stage_name = "script"

    async def execute(self, input_data) -> dict:
        """Generate script."""
        return {"status": "script_generated"}
