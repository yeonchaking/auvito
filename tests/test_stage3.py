"""Tests for Stage 3: Voice and Subtitles."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.contracts import NarrationContract, ScriptContract, ScriptSegment
from app.domain.schemas import STTRequest, TTSRequest
from app.providers.stt import OpenAISTTProvider, TranscriptWord
from app.providers.tts import EdgeTTSProvider, VoiceSynthesisResult
from app.providers.base import ProviderCallContext, ProviderMeta
from app.stages.stage3_voice import VoiceStage, VoiceStageInput
from app.utils.srt import SRTGenerator, SRTSubtitle
from decimal import Decimal
from datetime import datetime


@pytest.fixture
def script_contract():
    """Create a sample script contract for testing."""
    return ScriptContract(
        contract_type="script",
        schema_version="1.0",
        contract_id="scr_test123",
        run_id="run_test123",
        generated_by_stage_run_id="stg_test_1",
        created_at=datetime.utcnow(),
        language="ko-KR",
        title="Test Video",
        target_duration_sec=60,
        segments=[
            ScriptSegment(
                segment_id="seg_001",
                order=1,
                purpose="hook",
                text="안녕하세요 여러분",
                est_duration_sec=3.0,
            ),
            ScriptSegment(
                segment_id="seg_002",
                order=2,
                purpose="body",
                text="이것은 테스트 비디오입니다",
                est_duration_sec=50.0,
            ),
            ScriptSegment(
                segment_id="seg_003",
                order=3,
                purpose="cta",
                text="구독해주세요",
                est_duration_sec=7.0,
            ),
        ],
    )


class TestSRTGenerator:
    """Test SRT generation utilities."""

    def test_srt_subtitle_formatting(self):
        """Test SRT subtitle block formatting."""
        subtitle = SRTSubtitle(
            index=1,
            start_sec=0.0,
            end_sec=5.5,
            text="첫 번째 자막",
        )

        srt_block = subtitle.to_srt_block()
        assert "1" in srt_block
        assert "00:00:00,000 --> 00:00:05,500" in srt_block
        assert "첫 번째 자막" in srt_block

    def test_timecode_conversion(self):
        """Test seconds to SRT timecode conversion."""
        timecode = SRTSubtitle._seconds_to_timecode(3661.5)
        assert timecode == "01:01:01,500"

        timecode = SRTSubtitle._seconds_to_timecode(0.0)
        assert timecode == "00:00:00,000"

        timecode = SRTSubtitle._seconds_to_timecode(59.999)
        assert timecode == "00:00:59,999"

    def test_generate_from_words(self):
        """Test subtitle generation from word-level timestamps."""
        words = [
            {"word": "안녕하세요", "start_sec": 0.0, "end_sec": 0.5},
            {"word": "이것은", "start_sec": 0.5, "end_sec": 1.0},
            {"word": "테스트", "start_sec": 1.0, "end_sec": 1.5},
            {"word": "입니다", "start_sec": 1.5, "end_sec": 2.0},
        ]

        subtitles = SRTGenerator.generate_from_words(words)

        assert len(subtitles) > 0
        assert all(isinstance(s, SRTSubtitle) for s in subtitles)
        assert all(s.start_sec < s.end_sec for s in subtitles)
        assert subtitles[0].start_sec == 0.0
        assert subtitles[-1].end_sec == 2.0

    def test_generate_from_text_chunks(self):
        """Test subtitle generation from text chunks."""
        chunks = [
            {"text": "첫 번째 자막", "start_sec": 0.0, "end_sec": 3.0},
            {"text": "두 번째 자막", "start_sec": 3.0, "end_sec": 6.0},
        ]

        subtitles = SRTGenerator.generate_from_text_chunks(chunks)

        assert len(subtitles) == 2
        assert subtitles[0].text == "첫 번째 자막"
        assert subtitles[1].text == "두 번째 자막"

    def test_srt_file_roundtrip(self, tmp_path):
        """Test writing and reading SRT files."""
        subtitles = [
            SRTSubtitle(1, 0.0, 3.0, "첫 번째"),
            SRTSubtitle(2, 3.0, 6.0, "두 번째"),
        ]

        output_path = tmp_path / "test.srt"
        result = SRTGenerator.write_srt_file(subtitles, str(output_path))
        assert result is True
        assert output_path.exists()

        # Read back
        read_subtitles = SRTGenerator.read_srt_file(str(output_path))
        assert len(read_subtitles) == 2
        assert read_subtitles[0].text == "첫 번째"
        assert read_subtitles[1].text == "두 번째"

    def test_srt_timecode_parsing(self):
        """Test parsing SRT timecodes back to seconds."""
        seconds = SRTGenerator._timecode_to_seconds("01:02:03,456")
        assert seconds == pytest.approx(3723.456, abs=0.001)


class TestEdgeTTSProvider:
    """Test Edge TTS provider."""

    @pytest.mark.asyncio
    async def test_cost_estimation(self):
        """Test that Edge TTS is free."""
        provider = EdgeTTSProvider()
        request = TTSRequest(
            text="Test text",
            voice_id="ko-KR-SunHiNeural",
            language="ko-KR",
            speaking_rate=1.0,
        )
        ctx = ProviderCallContext(
            run_id="test",
            stage_run_id="test_1",
            attempt_no=1,
            idempotency_key="test",
        )

        cost = await provider.estimate_cost(request, ctx)
        assert cost.estimated_cost_usd == Decimal("0")
        assert cost.confidence == "high"

    @pytest.mark.asyncio
    async def test_synthesize_caching(self, tmp_path):
        """Test that TTS caches identical texts."""
        provider = EdgeTTSProvider(workspace_root=str(tmp_path))

        request = TTSRequest(
            text="Test text",
            voice_id="ko-KR-SunHiNeural",
            language="ko-KR",
            speaking_rate=1.0,
        )
        ctx = ProviderCallContext(
            run_id="test",
            stage_run_id="test_1",
            attempt_no=1,
            idempotency_key="test1",
        )

        # Mock the synthesize method to avoid actual API calls
        with patch("edge_tts.Communicate") as mock_communicate:
            mock_instance = AsyncMock()
            mock_communicate.return_value = mock_instance

            # First call
            with patch.object(provider, "_get_audio_duration", return_value=2.0):
                result1 = await provider.synthesize(request, ctx)

            # Second call should use cache
            result2 = await provider.synthesize(request, ctx)

            # Both should have same path (cache hit)
            assert result1.audio_path == result2.audio_path


class TestOpenAISTTProvider:
    """Test OpenAI STT provider."""

    @pytest.mark.asyncio
    async def test_cost_estimation(self):
        """Test STT cost estimation."""
        provider = OpenAISTTProvider(api_key="dummy_key")

        with patch.object(provider.ffmpeg_service, "get_duration", return_value=60.0):
            request = STTRequest(
                audio_path="/path/to/audio.wav",
                language="ko-KR",
            )
            ctx = ProviderCallContext(
                run_id="test",
                stage_run_id="test_1",
                attempt_no=1,
                idempotency_key="test",
            )

            cost = await provider.estimate_cost(request, ctx)
            # $0.006 per minute × 1 minute = $0.006
            assert cost.estimated_cost_usd == Decimal("0.006")

    @pytest.mark.asyncio
    async def test_fallback_mode(self):
        """Test STT fallback when API key missing."""
        provider = OpenAISTTProvider(api_key=None)
        assert provider.fallback_mode is True

        request = STTRequest(
            audio_path="/path/to/audio.wav",
            language="ko-KR",
        )
        ctx = ProviderCallContext(
            run_id="test",
            stage_run_id="test_1",
            attempt_no=1,
            idempotency_key="test",
        )

        with patch.object(provider.ffmpeg_service, "get_duration", return_value=10.0):
            result = await provider.transcribe(request, ctx)

            assert result.confidence == 0.0
            assert result.meta.metadata.get("fallback") is True
            assert result.meta.actual_cost_usd == Decimal("0")

    @pytest.mark.asyncio
    async def test_word_boundary_generation(self):
        """Test word boundary estimation."""
        provider = OpenAISTTProvider(fallback_mode=True)

        words = await provider._generate_word_boundaries("안녕하세요 테스트 입니다", 3.0)

        assert len(words) == 3
        assert words[0].word == "안녕하세요"
        assert words[0].start_sec == 0.0
        assert words[-1].end_sec == 3.0


class TestVoiceStage:
    """Test Voice Stage orchestration."""

    @pytest.mark.asyncio
    async def test_clip_timing_calculation(self, script_contract):
        """Test that clip timings are calculated correctly."""
        stage = VoiceStage()

        clips = [
            MagicMock(
                clip_id="clip_001",
                actual_duration_sec=3.0,
            ),
            MagicMock(
                clip_id="clip_002",
                actual_duration_sec=50.0,
            ),
            MagicMock(
                clip_id="clip_003",
                actual_duration_sec=7.0,
            ),
        ]

        await stage._update_clip_timings(clips, "/path/to/audio.wav")

        assert clips[0].start_sec == 0.0
        assert clips[0].end_sec == 3.0

        assert clips[1].start_sec == 3.0
        assert clips[1].end_sec == 53.0

        assert clips[2].start_sec == 53.0
        assert clips[2].end_sec == 60.0

    @pytest.mark.asyncio
    async def test_narration_contract_creation(self, script_contract):
        """Test NarrationContract creation."""
        stage = VoiceStage()

        # The contract creation happens inside execute(), but we can verify
        # the structure matches expectations
        contract = NarrationContract(
            contract_type="narration",
            schema_version="1.0",
            contract_id="nar_test123",
            run_id="run_test123",
            generated_by_stage_run_id="stg_test_1",
            created_at=datetime.utcnow(),
            script_id=script_contract.contract_id,
            language="ko-KR",
            narration_audio_uri="artifacts/audio/narration.wav",
            subtitles_uri="artifacts/subtitles/subtitles.srt",
            total_duration_sec=60.0,
            voice={
                "provider": "edge_tts",
                "voice_id": "ko-KR-SunHiNeural",
                "speaking_rate": 1.0,
            },
            audio_format="wav",
            sample_rate_hz=24000,
            clips=[],
        )

        assert contract.contract_type == "narration"
        assert contract.audio_format == "wav"
        assert contract.sample_rate_hz == 24000


class TestIntegration:
    """Integration tests for Stage 3."""

    @pytest.mark.asyncio
    async def test_voice_stage_input_structure(self, script_contract):
        """Test VoiceStageInput construction and usage."""
        input_data = VoiceStageInput(
            script_contract=script_contract,
            workspace_root="/workspace",
            openai_api_key="sk_test",
            tts_voice="ko-KR-SunHiNeural",
            speaking_rate=1.0,
        )

        assert input_data.script_contract == script_contract
        assert input_data.workspace_root == "/workspace"
        assert input_data.tts_voice == "ko-KR-SunHiNeural"
        assert input_data.speaking_rate == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
