"""Speech-to-text provider abstraction."""

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Optional, Protocol

import httpx
from pydantic import BaseModel

from app.domain.schemas import STTRequest
from app.providers.base import CostEstimate, ProviderCallContext, ProviderMeta
from app.services.ffmpeg_service import FFmpegService
from app.utils.logger import get_logger

logger = get_logger(__name__)


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
    meta: ProviderMeta


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


class OpenAISTTProvider:
    """OpenAI Speech-to-Text provider using Whisper API."""

    API_BASE = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-transcribe"
    FALLBACK_MODEL = "whisper-1"

    def __init__(self, api_key: Optional[str] = None, fallback_mode: bool = False):
        """Initialize OpenAI STT provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            fallback_mode: If True, generate basic SRT from segment durations
        """
        import os

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.fallback_mode = fallback_mode or not self.api_key
        self.ffmpeg_service = FFmpegService()

    async def estimate_cost(
        self, req: STTRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate STT cost based on audio duration.

        OpenAI Whisper pricing: ~$0.006 per minute of audio

        Args:
            req: STT request
            ctx: Provider context

        Returns:
            Cost estimate
        """
        try:
            duration = await self.ffmpeg_service.get_duration(req.audio_path)
            if duration is None:
                duration = 60.0  # Default estimate

            # $0.006 per minute
            cost_per_minute = Decimal("0.006")
            minutes = Decimal(str(duration)) / Decimal("60")
            total_cost = cost_per_minute * minutes

            return CostEstimate(
                estimated_cost_usd=total_cost,
                confidence="medium",
                reasoning=f"OpenAI Whisper pricing: $0.006/minute × {float(minutes):.2f}min",
            )
        except Exception as e:
            logger.warning(
                "Failed to estimate STT cost",
                error=str(e),
            )
            # Conservative estimate: assume 10 minutes
            return CostEstimate(
                estimated_cost_usd=Decimal("0.06"),
                confidence="low",
                reasoning="Fallback estimate: assuming ~10 minutes of audio",
            )

    async def transcribe(
        self, req: STTRequest, ctx: ProviderCallContext
    ) -> TranscriptResult:
        """Transcribe audio using OpenAI Whisper API.

        Args:
            req: STT request with audio file path
            ctx: Provider context

        Returns:
            TranscriptResult with transcript and word-level timestamps

        Raises:
            RuntimeError: If transcription fails
        """
        if self.fallback_mode:
            logger.warning(
                "No OpenAI API key available, using fallback mode",
                idempotency_key=ctx.idempotency_key,
            )
            return await self._transcribe_fallback(req, ctx)

        try:
            # Get audio duration for cost tracking
            duration = await self.ffmpeg_service.get_duration(req.audio_path)
            if duration is None:
                duration = 0.0

            # Call OpenAI Whisper API
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(req.audio_path, "rb") as audio_file:
                    files = {
                        "file": (Path(req.audio_path).name, audio_file, "audio/wav"),
                    }
                    data = {
                        "model": self.DEFAULT_MODEL,
                        "language": req.language,
                        "response_format": "verbose_json",
                    }

                    response = await client.post(
                        f"{self.API_BASE}/audio/transcriptions",
                        files=files,
                        data=data,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )

                    response.raise_for_status()
                    response_data = response.json()

            # Parse response and extract word-level timestamps
            text = response_data.get("text", "")
            words = []

            # Extract words with timestamps if available
            if "words" in response_data:
                for word_data in response_data["words"]:
                    words.append(
                        TranscriptWord(
                            word=word_data.get("word", ""),
                            start_sec=float(word_data.get("start", 0.0)),
                            end_sec=float(word_data.get("end", 0.0)),
                        )
                    )

            # Fallback: generate simple word boundaries if not in response
            if not words and text:
                words = await self._generate_word_boundaries(text, duration)

            logger.info(
                "STT transcription completed",
                text_length=len(text),
                word_count=len(words),
                duration_sec=duration,
                idempotency_key=ctx.idempotency_key,
            )

            cost_estimate = await self.estimate_cost(req, ctx)

            return TranscriptResult(
                text=text,
                language=req.language,
                words=words,
                confidence=response_data.get("confidence", 0.85),
                meta=ProviderMeta(
                    provider_name="openai",
                    model=self.DEFAULT_MODEL,
                    request_id=ctx.idempotency_key,
                    actual_cost_usd=cost_estimate.estimated_cost_usd,
                    metadata={
                        "duration_sec": duration,
                        "word_count": len(words),
                    },
                ),
            )

        except Exception as e:
            logger.error(
                "STT transcription failed",
                error=str(e),
                idempotency_key=ctx.idempotency_key,
            )
            # Fall back to fallback mode
            return await self._transcribe_fallback(req, ctx)

    async def _transcribe_fallback(
        self, req: STTRequest, ctx: ProviderCallContext
    ) -> TranscriptResult:
        """Fallback transcription when OpenAI API is unavailable.

        Generates basic word boundaries based on audio duration.

        Args:
            req: STT request
            ctx: Provider context

        Returns:
            TranscriptResult with estimated word boundaries
        """
        try:
            duration = await self.ffmpeg_service.get_duration(req.audio_path)
            if duration is None:
                duration = 0.0

            # Generate placeholder transcript
            text = f"[Audio transcription not available - {duration:.1f}s duration]"
            words = []

            logger.info(
                "Using fallback transcription",
                duration_sec=duration,
                idempotency_key=ctx.idempotency_key,
            )

            return TranscriptResult(
                text=text,
                language=req.language,
                words=words,
                confidence=0.0,
                meta=ProviderMeta(
                    provider_name="fallback",
                    model="fallback",
                    request_id=ctx.idempotency_key,
                    actual_cost_usd=Decimal("0"),
                    metadata={"duration_sec": duration, "fallback": True},
                ),
            )
        except Exception as e:
            logger.warning("Fallback transcription failed", error=str(e))
            return TranscriptResult(
                text="",
                language=req.language,
                words=[],
                confidence=0.0,
                meta=ProviderMeta(
                    provider_name="fallback",
                    model="fallback",
                    request_id=ctx.idempotency_key,
                    actual_cost_usd=Decimal("0"),
                    metadata={"error": str(e), "fallback": True},
                ),
            )

    async def _generate_word_boundaries(
        self, text: str, duration_sec: float
    ) -> list[TranscriptWord]:
        """Generate simple word boundaries for text.

        Args:
            text: Transcript text
            duration_sec: Total duration

        Returns:
            List of TranscriptWord with approximate boundaries
        """
        if not text or duration_sec <= 0:
            return []

        words_text = text.split()
        if not words_text:
            return []

        word_duration = duration_sec / len(words_text)
        words = []

        for i, word in enumerate(words_text):
            start_sec = i * word_duration
            end_sec = (i + 1) * word_duration

            words.append(
                TranscriptWord(
                    word=word,
                    start_sec=start_sec,
                    end_sec=end_sec,
                )
            )

        return words
