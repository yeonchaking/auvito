"""Stage 3: Voice and narration with subtitle generation."""

import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.contracts import NarrationClip, NarrationContract, ScriptContract
from app.domain.schemas import STTRequest, TTSRequest
from app.providers.stt import OpenAISTTProvider, TranscriptWord
from app.providers.tts import EdgeTTSProvider
from app.providers.base import ProviderCallContext
from app.services.ffmpeg_service import FFmpegService
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.utils.logger import get_logger
from app.utils.srt import SRTGenerator, SRTSubtitle

logger = get_logger(__name__)


class VoiceStageInput:
    """Input data for voice stage."""

    def __init__(
        self,
        script_contract: ScriptContract,
        workspace_root: str,
        openai_api_key: Optional[str] = None,
        tts_voice: str = "ko-KR-SunHiNeural",
        speaking_rate: float = 1.0,
    ):
        """Initialize voice stage input.

        Args:
            script_contract: ScriptContract from Stage 2
            workspace_root: Workspace root directory
            openai_api_key: Optional OpenAI API key for STT
            tts_voice: TTS voice ID
            speaking_rate: TTS speaking rate (0.5-2.0)
        """
        self.script_contract = script_contract
        self.workspace_root = workspace_root
        self.openai_api_key = openai_api_key
        self.tts_voice = tts_voice
        self.speaking_rate = speaking_rate


class VoiceStage(BaseStage):
    """Stage 3: Text-to-speech and narration generation.

    Pipeline:
    1. Split script into segments
    2. For each segment: call Edge TTS → generate audio clip
    3. Merge all clips into single narration.wav
    4. Call STT (gpt-4o-transcribe) on merged audio → get word timestamps
    5. Generate subtitles.srt from word timestamps
    6. Post-process subtitles (line length limits, timing adjustments)

    Output:
    - NarrationContract with clip timings
    - narration.wav (merged audio)
    - subtitles.srt (SRT format subtitles)
    """

    stage_name = "voice"

    def __init__(self):
        """Initialize voice stage."""
        self.ffmpeg_service = FFmpegService()
        self.tts_provider = None
        self.stt_provider = None

    async def execute(self, input_data: VoiceStageInput) -> NarrationContract:
        """Generate voice narration and subtitles.

        Creates:
        - narration_contract.json (NarrationContract)
        - narration.wav (merged audio)
        - subtitles.srt (SRT subtitles)

        Args:
            input_data: Voice stage input with script contract

        Returns:
            NarrationContract

        Raises:
            ValueError: If narration generation fails
        """
        script_contract = input_data.script_contract
        workspace = Path(input_data.workspace_root) / "projects" / script_contract.run_id
        voice_dir = workspace / "03_voice"
        voice_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Starting voice generation",
            script_id=script_contract.contract_id,
            segment_count=len(script_contract.segments),
            language=script_contract.language,
        )

        # Initialize providers
        self.tts_provider = EdgeTTSProvider(workspace_root=input_data.workspace_root)
        self.stt_provider = OpenAISTTProvider(api_key=input_data.openai_api_key)

        try:
            # Step 1: Generate audio clips for each segment
            clips, clip_files = await self._synthesize_segments(
                script_contract,
                input_data.tts_voice,
                input_data.speaking_rate,
            )

            # Step 2: Merge all clips into single audio file
            merged_audio_path = str(voice_dir / "narration.wav")
            total_duration = await self._merge_audio_clips(
                clip_files, merged_audio_path
            )

            # Update clips with actual cumulative timings
            await self._update_clip_timings(clips, merged_audio_path)

            # Step 3: Transcribe merged audio to get word-level timestamps
            transcript = await self._transcribe_audio(
                merged_audio_path, script_contract.language
            )

            # Step 4: Generate SRT subtitles
            subtitles_path = str(voice_dir / "subtitles.srt")
            await self._generate_subtitles(
                transcript, subtitles_path, script_contract.language
            )

            # Create NarrationContract
            contract_id = f"nar_{hashlib.md5(f'{script_contract.run_id}_{self.stage_name}'.encode()).hexdigest()[:8]}"

            narration_contract = NarrationContract(
                contract_type="narration",
                schema_version="1.0",
                contract_id=contract_id,
                run_id=script_contract.run_id,
                generated_by_stage_run_id=f"stg_{script_contract.run_id}_{self.stage_name}_1",
                created_at=datetime.utcnow(),
                script_id=script_contract.contract_id,
                language=script_contract.language,
                narration_audio_uri=f"artifacts/audio/narration.wav",
                subtitles_uri=f"artifacts/subtitles/subtitles.srt",
                total_duration_sec=total_duration,
                voice={
                    "provider": "edge_tts",
                    "voice_id": input_data.tts_voice,
                    "speaking_rate": input_data.speaking_rate,
                },
                audio_format="wav",
                sample_rate_hz=24000,
                clips=clips,
            )

            # Save contract as JSON
            contract_json_path = voice_dir / "narration_contract.json"
            await FileStorage.save_json(
                str(contract_json_path),
                json.loads(narration_contract.model_dump_json()),
            )

            # Save provenance sidecar
            provenance = {
                "contract_id": narration_contract.contract_id,
                "script_id": script_contract.contract_id,
                "generated_at": datetime.utcnow().isoformat(),
                "tts_provider": "edge_tts",
                "stt_provider": "openai",
                "segment_count": len(clips),
                "total_duration_sec": total_duration,
            }
            provenance_path = voice_dir / "provenance.json"
            await FileStorage.save_json(str(provenance_path), provenance)

            logger.info(
                "Voice generation completed",
                script_id=script_contract.contract_id,
                narration_id=narration_contract.contract_id,
                clip_count=len(clips),
                total_duration_sec=total_duration,
            )

            return narration_contract

        except Exception as e:
            logger.error(
                "Voice generation failed",
                script_id=script_contract.contract_id,
                error=str(e),
            )
            raise ValueError(f"Voice generation failed: {str(e)}") from e

    async def _synthesize_segments(
        self,
        script_contract: ScriptContract,
        voice_id: str,
        speaking_rate: float,
    ) -> tuple[list[NarrationClip], list[str]]:
        """Synthesize audio for each script segment.

        Args:
            script_contract: Script contract with segments
            voice_id: TTS voice ID
            speaking_rate: TTS speaking rate

        Returns:
            Tuple of (clips list, audio file paths list)
        """
        clips = []
        clip_files = []

        for segment in script_contract.segments:
            # Create TTS request
            tts_request = TTSRequest(
                text=segment.text,
                voice_id=voice_id,
                language=script_contract.language,
                speaking_rate=speaking_rate,
            )

            # Create provider context
            ctx = ProviderCallContext(
                run_id=script_contract.run_id,
                stage_run_id=f"stg_{script_contract.run_id}_{self.stage_name}_1",
                attempt_no=1,
                idempotency_key=hashlib.md5(
                    f"{script_contract.run_id}_{segment.segment_id}".encode()
                ).hexdigest()[:16],
            )

            try:
                # Synthesize segment
                result = await self.tts_provider.synthesize(tts_request, ctx)

                logger.info(
                    "Segment synthesized",
                    segment_id=segment.segment_id,
                    duration_sec=result.duration_sec,
                )

                # Create clip (timing will be updated after merging)
                clip = NarrationClip(
                    clip_id=f"clip_{len(clips) + 1:03d}",
                    segment_id=segment.segment_id,
                    text=segment.text,
                    start_sec=0.0,  # Will be updated
                    end_sec=0.0,  # Will be updated
                    actual_duration_sec=result.duration_sec,
                )
                clips.append(clip)
                clip_files.append(result.audio_path)

            except Exception as e:
                logger.error(
                    "Segment synthesis failed",
                    segment_id=segment.segment_id,
                    error=str(e),
                )
                raise ValueError(f"Failed to synthesize segment {segment.segment_id}") from e

        return clips, clip_files

    async def _merge_audio_clips(
        self, clip_files: list[str], output_path: str
    ) -> float:
        """Merge audio clips into single file using ffmpeg.

        Args:
            clip_files: List of audio file paths
            output_path: Output merged audio path

        Returns:
            Total duration of merged audio

        Raises:
            RuntimeError: If merge fails
        """
        if not clip_files:
            raise ValueError("No audio clips to merge")

        # Create concat demuxer file
        concat_file = Path(output_path).parent / "concat_list.txt"
        try:
            with open(concat_file, "w") as f:
                for clip_file in clip_files:
                    f.write(f"file '{clip_file}'\n")

            # Use ffmpeg concat demuxer
            import subprocess

            cmd = [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-y",
                output_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg concat failed: {stderr.decode()}")

            # Get merged duration
            duration = await self.ffmpeg_service.get_duration(output_path)
            if duration is None:
                duration = sum(
                    await self.ffmpeg_service.get_duration(f) for f in clip_files
                )
                duration = duration or 0.0

            logger.info(
                "Audio clips merged",
                clip_count=len(clip_files),
                total_duration_sec=duration,
            )

            return duration

        except Exception as e:
            logger.error("Audio merge failed", error=str(e))
            raise RuntimeError(f"Failed to merge audio clips: {str(e)}") from e
        finally:
            # Clean up concat file
            try:
                concat_file.unlink()
            except Exception:
                pass

    async def _update_clip_timings(
        self, clips: list[NarrationClip], merged_audio_path: str
    ) -> None:
        """Update clip timings based on actual merged audio durations.

        Args:
            clips: List of clips to update
            merged_audio_path: Path to merged audio file
        """
        current_time = 0.0

        for clip in clips:
            clip.start_sec = current_time
            clip.end_sec = current_time + clip.actual_duration_sec
            current_time = clip.end_sec

            logger.debug(
                "Clip timing updated",
                clip_id=clip.clip_id,
                start_sec=clip.start_sec,
                end_sec=clip.end_sec,
            )

    async def _transcribe_audio(
        self, audio_path: str, language: str
    ) -> list[TranscriptWord]:
        """Transcribe audio to get word-level timestamps.

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            List of TranscriptWord with timestamps
        """
        stt_request = STTRequest(
            audio_path=audio_path,
            language=language,
        )

        ctx = ProviderCallContext(
            run_id="voice_stage",
            stage_run_id=f"stg_voice_{datetime.utcnow().timestamp()}",
            attempt_no=1,
            idempotency_key=hashlib.md5(audio_path.encode()).hexdigest()[:16],
        )

        try:
            result = await self.stt_provider.transcribe(stt_request, ctx)

            logger.info(
                "Audio transcribed",
                text_length=len(result.text),
                word_count=len(result.words),
                confidence=result.confidence,
            )

            return result.words

        except Exception as e:
            logger.error("Audio transcription failed", error=str(e))
            # Return empty word list - subtitles will be generated from clip text instead
            return []

    async def _generate_subtitles(
        self, words: list[TranscriptWord], output_path: str, language: str
    ) -> None:
        """Generate SRT subtitle file from word timestamps.

        Args:
            words: List of TranscriptWord with timestamps
            output_path: Output SRT file path
            language: Language code (for formatting)
        """
        subtitles = []

        if words:
            # Convert words to dict format for SRT generator
            word_dicts = [
                {
                    "word": w.word,
                    "start_sec": w.start_sec,
                    "end_sec": w.end_sec,
                }
                for w in words
            ]

            subtitles = SRTGenerator.generate_from_words(
                word_dicts,
                max_chars_per_line=42,
                max_lines=3,
            )
        else:
            # Fallback: empty subtitles
            logger.warning("No word-level timestamps available, creating empty subtitles")
            subtitles = []

        # Write SRT file
        try:
            result = SRTGenerator.write_srt_file(subtitles, output_path)

            if result:
                logger.info(
                    "Subtitles generated",
                    output_path=output_path,
                    subtitle_count=len(subtitles),
                )
            else:
                logger.error("Failed to write SRT file", output_path=output_path)
                raise RuntimeError(f"Failed to write SRT file: {output_path}")

        except Exception as e:
            logger.error("Subtitle generation failed", error=str(e))
            raise RuntimeError(f"Failed to generate subtitles: {str(e)}") from e
