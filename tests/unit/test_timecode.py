"""Tests for timecode utilities."""

import pytest

from app.utils.timecode import seconds_to_timecode, timecode_to_seconds


def test_seconds_to_timecode():
    """Test seconds to timecode conversion."""
    assert seconds_to_timecode(0) == "00:00:00.000"
    assert seconds_to_timecode(65.5) == "00:01:05.500"
    assert seconds_to_timecode(3661.25) == "01:01:01.250"


def test_timecode_to_seconds():
    """Test timecode to seconds conversion."""
    assert timecode_to_seconds("00:00:00.000") == 0
    assert timecode_to_seconds("00:01:05.500") == 65.5
    assert timecode_to_seconds("01:01:01.250") == 3661.25


def test_timecode_roundtrip():
    """Test roundtrip conversion."""
    original = 480.5
    timecode = seconds_to_timecode(original)
    recovered = timecode_to_seconds(timecode)
    assert abs(recovered - original) < 0.01
