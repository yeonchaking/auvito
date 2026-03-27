"""Stage 3: Voice and narration."""

from app.stages.base import BaseStage


class VoiceStage(BaseStage):
    """Stage 3: Text-to-speech and narration."""

    stage_name = "voice"

    async def execute(self, input_data) -> dict:
        """Generate voice narration."""
        return {"status": "voice_generated"}
