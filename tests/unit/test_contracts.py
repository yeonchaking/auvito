"""Tests for stage contracts."""

from datetime import datetime

import pytest

from app.domain.contracts import (
    ScriptContract,
    ScriptSegment,
    NarrationContract,
    StoryboardContract,
)


def test_script_contract_creation():
    """Test script contract creation."""
    segments = [
        ScriptSegment(
            segment_id="seg_001",
            order=1,
            purpose="hook",
            text="Hook text",
            est_duration_sec=10.0,
        )
    ]

    contract = ScriptContract(
        contract_id="script_123",
        run_id="run_123",
        generated_by_stage_run_id="stg_123",
        created_at=datetime.utcnow(),
        language="ko-KR",
        title="Test Script",
        target_duration_sec=480,
        segments=segments,
    )

    assert contract.language == "ko-KR"
    assert len(contract.segments) == 1
    assert contract.segments[0].purpose == "hook"


def test_narration_contract_creation():
    """Test narration contract creation."""
    from app.domain.contracts import NarrationClip

    clips = [
        NarrationClip(
            clip_id="clip_001",
            segment_id="seg_001",
            text="Narration text",
            start_sec=0.0,
            end_sec=5.0,
            actual_duration_sec=5.0,
        )
    ]

    contract = NarrationContract(
        contract_id="nar_123",
        run_id="run_123",
        generated_by_stage_run_id="stg_123",
        created_at=datetime.utcnow(),
        script_id="script_123",
        language="ko-KR",
        narration_audio_uri="artifacts/audio.wav",
        subtitles_uri="artifacts/subs.srt",
        total_duration_sec=5.0,
        voice={"provider": "edge_tts"},
        audio_format="wav",
        sample_rate_hz=24000,
        clips=clips,
    )

    assert contract.total_duration_sec == 5.0
    assert len(contract.clips) == 1
