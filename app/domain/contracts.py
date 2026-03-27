"""Stage contracts and schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel


class ContractEnvelope(BaseModel):
    """Base envelope for all contracts."""

    contract_type: str
    schema_version: str
    contract_id: str
    run_id: str
    generated_by_stage_run_id: str
    created_at: datetime


class BenchmarkReportSegment(BaseModel):
    """Segment analysis in benchmark report."""

    segment_id: str
    video_id: str
    metric: str
    value: float
    percentile: Optional[float] = None


class BenchmarkReport(ContractEnvelope):
    """Benchmark analysis report from Stage 1."""

    contract_type: Literal["benchmark_report"] = "benchmark_report"
    schema_version: str = "1.0"

    niche: str
    analyzed_video_count: int
    analysis_period_days: int
    transcript_available: bool
    analysis_confidence: Literal["high", "medium", "low"]

    top_patterns: dict[str, Any]
    keyword_bank: dict[str, Any]
    competitor_analysis: dict[str, Any]
    ctr_insights: dict[str, Any]


class ScriptSegment(BaseModel):
    """Script segment."""

    segment_id: str
    order: int
    purpose: Literal["hook", "body", "cta"]
    text: str
    est_duration_sec: float


class ScriptContract(ContractEnvelope):
    """Script contract from Stage 2."""

    contract_type: Literal["script"] = "script"
    schema_version: str = "1.0"

    language: str
    title: str
    target_duration_sec: int
    segments: list[ScriptSegment]


class NarrationClip(BaseModel):
    """Narration clip mapping."""

    clip_id: str
    segment_id: str
    text: str
    start_sec: float
    end_sec: float
    actual_duration_sec: float
    ssml: Optional[str] = None


class NarrationContract(ContractEnvelope):
    """Narration contract from Stage 3."""

    contract_type: Literal["narration"] = "narration"
    schema_version: str = "1.0"

    script_id: str
    language: str
    narration_audio_uri: str
    subtitles_uri: str
    total_duration_sec: float

    voice: dict[str, Any]
    audio_format: str
    sample_rate_hz: int

    clips: list[NarrationClip]


class StoryboardShot(BaseModel):
    """Storyboard shot."""

    shot_id: str
    order: int
    start_sec: float
    end_sec: float
    narration_clip_ids: list[str]
    visual_kind: Literal["image", "video"]
    prompt: str
    motion_hint: Optional[str] = None


class StoryboardContract(ContractEnvelope):
    """Storyboard contract from Stage 4."""

    contract_type: Literal["storyboard"] = "storyboard"
    schema_version: str = "1.0"

    script_id: str
    narration_id: str
    aspect_ratio: str
    total_duration_sec: float
    shots: list[StoryboardShot]


class AssetManifestAsset(BaseModel):
    """Asset in manifest."""

    asset_id: str
    shot_id: str
    kind: Literal["image", "video"]
    source_type: Literal["generated", "stock", "local"]
    uri: str
    width: int
    height: int
    duration_sec: Optional[float] = None


class AssetManifestContract(ContractEnvelope):
    """Asset manifest contract from Stage 5."""

    contract_type: Literal["asset_manifest"] = "asset_manifest"
    schema_version: str = "1.0"

    storyboard_id: str
    selected_assets: list[AssetManifestAsset]


class RenderOutput(BaseModel):
    """Render output configuration."""

    aspect_ratio: str
    width: int
    height: int
    fps: int
    video_codec: str
    audio_codec: str
    draft_output_uri: str
    final_output_uri: str
    final_duration_sec: float


class RenderNarrationTrack(BaseModel):
    """Narration track for render."""

    uri: str


class RenderTimelineItem(BaseModel):
    """Timeline item for render."""

    item_id: str
    shot_id: str
    asset_id: str
    start_sec: float
    end_sec: float
    motion_preset: str


class RenderSubtitles(BaseModel):
    """Subtitle configuration for render."""

    uri: str
    burn_in: bool


class RenderPlanContract(ContractEnvelope):
    """Render plan contract from Stage 6."""

    contract_type: Literal["render_plan"] = "render_plan"
    schema_version: str = "1.0"

    storyboard_id: str
    asset_manifest_id: str

    output: RenderOutput
    narration_track: RenderNarrationTrack
    timeline_items: list[RenderTimelineItem]
    subtitles: RenderSubtitles


class UploadMetadataContract(ContractEnvelope):
    """Upload metadata contract from Stage 8."""

    contract_type: Literal["upload_metadata"] = "upload_metadata"
    schema_version: str = "1.0"

    platform: str
    title: str
    description: str
    tags: list[str]
    visibility: Literal["private", "unlisted", "public"]
    category_id: int
    default_language: str
    made_for_kids: bool
    publish_at: Optional[datetime] = None
