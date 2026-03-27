"""Timecode utilities."""


def seconds_to_timecode(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def timecode_to_seconds(timecode: str) -> float:
    """Convert HH:MM:SS.mmm format to seconds."""
    parts = timecode.split(":")
    hours = int(parts[0]) if len(parts) > 2 else 0
    minutes = int(parts[-2])
    seconds = float(parts[-1])

    return hours * 3600 + minutes * 60 + seconds
