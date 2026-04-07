"""LLM output validation schemas."""

from typing import Any, Optional

from pydantic import BaseModel


class BenchmarkRequest(BaseModel):
    """Benchmark request schema."""

    topic: str
    niche: str
    search_keywords: list[str]
    max_videos: int = 10


class ScriptRequest(BaseModel):
    """Script generation request schema."""

    benchmark_report_path: str
    title_seed: str
    target_duration_sec: int
    niche: str
    channel_voice: Optional[dict[str, Any]] = None


class TTSRequest(BaseModel):
    """TTS request schema."""

    text: str
    voice_id: str
    language: str
    speaking_rate: float = 1.0


class STTRequest(BaseModel):
    """STT request schema."""

    audio_path: str
    language: str


class StoryboardRequest(BaseModel):
    """Storyboard generation request schema."""

    script_path: str
    narration_path: str
    niche: str


class ImageAssetRequest(BaseModel):
    """Image asset request schema."""

    prompt: str
    width: int = 1280
    height: int = 720
    style: Optional[str] = None
    shot_id: Optional[str] = None


class VideoAssetRequest(BaseModel):
    """Video asset request schema."""

    prompt: str
    duration_sec: float
    style: Optional[str] = None


class MetadataRequest(BaseModel):
    """Metadata generation request schema."""

    render_plan_path: str
    project_title: str
    niche: str
    keywords: list[str]


