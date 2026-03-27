"""Speech-to-text provider abstraction."""

from typing import Protocol

from pydantic import BaseModel

from app.domain.schemas import STTRequest
from app.providers.base import CostEstimate, ProviderCallContext


class TranscriptWord(BaseModel):
    """Word-level transcript."""

    word: str
    start_sec: float
    end_sec: float


class TranscriptResult(BaseModel):
    """Speech transcription result."""

    text: str
    language: str
    words: list[TranscriptWord] = []
    confidence: float
    meta: dict = {}


class STTProvider(Protocol):
    """Speech-to-text provider protocol."""

    async def estimate_cost(
        self, req: STTRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate STT cost."""
        ...

    async def transcribe(
        self, req: STTRequest, ctx: ProviderCallContext
    ) -> TranscriptResult:
        """Transcribe audio."""
        ...
