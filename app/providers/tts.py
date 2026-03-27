"""Text-to-speech provider abstraction."""

from typing import Protocol

from pydantic import BaseModel

from app.domain.schemas import TTSRequest
from app.providers.base import CostEstimate, ProviderCallContext


class VoiceSynthesisResult(BaseModel):
    """Voice synthesis result."""

    audio_path: str
    duration_sec: float
    format: str
    sample_rate_hz: int
    meta: dict = {}


class TTSProvider(Protocol):
    """Text-to-speech provider protocol."""

    async def estimate_cost(
        self, req: TTSRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate TTS cost."""
        ...

    async def synthesize(
        self, req: TTSRequest, ctx: ProviderCallContext
    ) -> VoiceSynthesisResult:
        """Synthesize text to speech."""
        ...
