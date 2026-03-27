"""Text-to-speech provider abstraction."""

import asyncio
import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

from app.domain.schemas import TTSRequest
from app.providers.base import CostEstimate, ProviderCallContext, ProviderMeta
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceSynthesisResult(BaseModel):
    """Voice synthesis result."""

    audio_path: str
    duration_sec: float
    format: str
    sample_rate_hz: int
    meta: ProviderMeta


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


class EdgeTTSProvider:
    """Edge TTS provider implementation using edge_tts library."""

    SAMPLE_RATE = 24000
    FORMAT = "wav"

    def __init__(self, workspace_root: str = "workspace"):
        """Initialize Edge TTS provider.

        Args:
            workspace_root: Root workspace directory for temp files
        """
        self.workspace_root = Path(workspace_root)
        self.temp_dir = self.workspace_root / "temp" / "tts"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def estimate_cost(
        self, req: TTSRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate TTS cost (Edge TTS is free).

        Args:
            req: TTS request
            ctx: Provider context

        Returns:
            Cost estimate (always $0 for Edge TTS)
        """
        return CostEstimate(
            estimated_cost_usd=Decimal("0"),
            confidence="high",
            reasoning="Edge TTS API is provided at no cost by Microsoft",
        )

    async def synthesize(
        self, req: TTSRequest, ctx: ProviderCallContext
    ) -> VoiceSynthesisResult:
        """Synthesize text to speech using Edge TTS.

        Args:
            req: TTS request with text and voice config
            ctx: Provider context

        Returns:
            VoiceSynthesisResult with audio file path and metadata

        Raises:
            RuntimeError: If synthesis fails
        """
        try:
            import edge_tts
        except ImportError:
            raise RuntimeError(
                "edge_tts not installed. Install with: pip install edge-tts"
            )

        # Generate output file path
        text_hash = hashlib.md5(req.text.encode()).hexdigest()[:8]
        output_filename = f"tts_{text_hash}_{req.voice_id.replace('-', '_')}.wav"
        output_path = str(self.temp_dir / output_filename)

        # Skip if already generated
        output_file = Path(output_path)
        if output_file.exists():
            duration = await self._get_audio_duration(output_path)
            return VoiceSynthesisResult(
                audio_path=output_path,
                duration_sec=duration,
                format=self.FORMAT,
                sample_rate_hz=self.SAMPLE_RATE,
                meta=ProviderMeta(
                    provider_name="edge_tts",
                    model="edge_tts",
                    request_id=ctx.idempotency_key,
                    metadata={"cached": True},
                ),
            )

        try:
            # Synthesize using Edge TTS
            communicate = edge_tts.Communicate(
                text=req.text,
                voice=req.voice_id,
                rate=f"{int((req.speaking_rate - 1) * 100):+d}%",  # Convert to ±XX% format
            )

            await communicate.save(output_path)

            # Get actual duration
            duration = await self._get_audio_duration(output_path)

            logger.info(
                "TTS synthesis completed",
                text_length=len(req.text),
                voice_id=req.voice_id,
                duration_sec=duration,
                idempotency_key=ctx.idempotency_key,
            )

            return VoiceSynthesisResult(
                audio_path=output_path,
                duration_sec=duration,
                format=self.FORMAT,
                sample_rate_hz=self.SAMPLE_RATE,
                meta=ProviderMeta(
                    provider_name="edge_tts",
                    model="edge_tts",
                    request_id=ctx.idempotency_key,
                    actual_cost_usd=Decimal("0"),
                    metadata={"text_length": len(req.text)},
                ),
            )

        except Exception as e:
            logger.error(
                "TTS synthesis failed",
                voice_id=req.voice_id,
                error=str(e),
                idempotency_key=ctx.idempotency_key,
            )
            raise RuntimeError(f"TTS synthesis failed: {str(e)}") from e

    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds using ffprobe.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds

        Raises:
            RuntimeError: If ffprobe fails or is not available
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise RuntimeError(f"ffprobe failed: {stderr.decode()}")

            duration_str = stdout.decode().strip()
            return float(duration_str) if duration_str else 0.0

        except Exception as e:
            logger.warning(
                "Failed to get audio duration, estimating",
                audio_path=audio_path,
                error=str(e),
            )
            # Fallback: estimate duration from file size (rough estimate)
            # WAV format: ~192 kbps for 24kHz mono PCM
            try:
                file_size = Path(audio_path).stat().st_size
                # WAV header is ~44 bytes, rest is audio
                audio_bytes = max(file_size - 44, 0)
                # 24000 Hz * 2 bytes per sample = 48000 bytes per second
                return audio_bytes / 48000
            except Exception:
                return 0.0
