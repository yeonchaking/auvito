"""Fake providers for testing."""

import json
import uuid
from datetime import datetime
from decimal import Decimal

from app.domain.contracts import (
    BenchmarkReport,
    NarrationClip,
    NarrationContract,
    ScriptContract,
    ScriptSegment,
    StoryboardContract,
    StoryboardShot,
)
from app.domain.schemas import (
    BenchmarkRequest,
    ScriptRequest,
    StoryboardRequest,
    STTRequest,
    TTSRequest,
)
from app.providers.asset import AssetJobHandle, AssetJobStatus, GeneratedAsset
from app.providers.base import CostEstimate, ProviderCallContext
from app.providers.narrative import ThumbnailCopyRequest, ThumbnailCopyResult
from app.providers.stt import TranscriptResult, TranscriptWord
from app.providers.tts import VoiceSynthesisResult


class FakeResearchProvider:
    """Fake research provider for testing."""

    async def estimate_cost(
        self, req: BenchmarkRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.10"))

    async def benchmark(
        self, req: BenchmarkRequest, ctx: ProviderCallContext
    ) -> BenchmarkReport:
        """Generate fake benchmark report."""
        return BenchmarkReport(
            contract_id=f"bench_{uuid.uuid4()}",
            run_id=ctx.run_id,
            generated_by_stage_run_id=ctx.stage_run_id,
            created_at=datetime.utcnow(),
            niche=req.niche,
            analyzed_video_count=10,
            analysis_period_days=30,
            transcript_available=True,
            analysis_confidence="high",
            top_patterns={
                "hook_length_sec": 3,
                "cta_placement": "end",
                "music_style": "epic",
            },
            keyword_bank={"keywords": ["주제", "콘텐츠"]},
            competitor_analysis={"competitors": ["채널1", "채널2"]},
            ctr_insights={"average_ctr": 0.05},
        )


class FakeNarrativeProvider:
    """Fake narrative provider for testing."""

    async def estimate_script_cost(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.05"))

    async def generate_script(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> ScriptContract:
        """Generate fake script."""
        return ScriptContract(
            contract_id=f"script_{uuid.uuid4()}",
            run_id=ctx.run_id,
            generated_by_stage_run_id=ctx.stage_run_id,
            created_at=datetime.utcnow(),
            language="ko-KR",
            title="Sample Script",
            target_duration_sec=480,
            segments=[
                ScriptSegment(
                    segment_id="seg_001",
                    order=1,
                    purpose="hook",
                    text="오늘은 흥미로운 주제를 다루겠습니다.",
                    est_duration_sec=10.0,
                ),
                ScriptSegment(
                    segment_id="seg_002",
                    order=2,
                    purpose="body",
                    text="본론 내용입니다.",
                    est_duration_sec=450.0,
                ),
                ScriptSegment(
                    segment_id="seg_003",
                    order=3,
                    purpose="cta",
                    text="구독 부탁드립니다.",
                    est_duration_sec=20.0,
                ),
            ],
        )

    async def estimate_storyboard_cost(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.05"))

    async def generate_storyboard(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> StoryboardContract:
        """Generate fake storyboard."""
        return StoryboardContract(
            contract_id=f"storyboard_{uuid.uuid4()}",
            run_id=ctx.run_id,
            generated_by_stage_run_id=ctx.stage_run_id,
            created_at=datetime.utcnow(),
            script_id="script_xxx",
            narration_id="narration_xxx",
            aspect_ratio="16:9",
            total_duration_sec=480,
            shots=[
                StoryboardShot(
                    shot_id="shot_001",
                    order=1,
                    start_sec=0,
                    end_sec=10,
                    narration_clip_ids=["clip_001"],
                    visual_kind="image",
                    prompt="Epic landscape background",
                    motion_hint="slow_zoom_in",
                ),
            ],
        )

    async def estimate_thumbnail_copy_cost(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.01"))

    async def generate_thumbnail_copy(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> ThumbnailCopyResult:
        """Generate fake thumbnail copy."""
        return ThumbnailCopyResult(
            headline="Shocking Discovery!", subheading="You won't believe..."
        )

class FakeTTSProvider:
    """Fake TTS provider for testing."""

    async def estimate_cost(
        self, req: TTSRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.01"))

    async def synthesize(
        self, req: TTSRequest, ctx: ProviderCallContext
    ) -> VoiceSynthesisResult:
        """Generate fake TTS result."""
        return VoiceSynthesisResult(
            audio_path="/tmp/audio.wav",
            duration_sec=5.0,
            format="wav",
            sample_rate_hz=24000,
        )


class FakeSTTProvider:
    """Fake STT provider for testing."""

    async def estimate_cost(
        self, req: STTRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.005"))

    async def transcribe(
        self, req: STTRequest, ctx: ProviderCallContext
    ) -> TranscriptResult:
        """Generate fake transcription."""
        return TranscriptResult(
            text="This is a test transcription.",
            language="en",
            words=[
                TranscriptWord(word="This", start_sec=0, end_sec=0.5),
                TranscriptWord(word="is", start_sec=0.5, end_sec=1),
            ],
            confidence=0.95,
        )


class FakeAssetProvider:
    """Fake asset provider for testing."""

    async def estimate_image_cost(
        self, req, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.02"))

    async def generate_image(
        self, req, ctx: ProviderCallContext
    ) -> GeneratedAsset:
        """Generate fake image."""
        return GeneratedAsset(
            asset_id=f"img_{uuid.uuid4()}",
            uri="/tmp/image.png",
            sha256="abc123",
            width=1280,
            height=720,
            format="png",
        )

    async def estimate_video_cost(
        self, req, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost."""
        return CostEstimate(estimated_cost_usd=Decimal("0.50"))

    async def submit_video(
        self, req, ctx: ProviderCallContext
    ) -> AssetJobHandle:
        """Submit video job."""
        return AssetJobHandle(
            job_id=f"job_{uuid.uuid4()}",
            status="SUBMITTED",
            created_at=datetime.utcnow().isoformat(),
        )

    async def get_video_status(
        self, job_id: str, ctx: ProviderCallContext
    ) -> AssetJobStatus:
        """Get video status."""
        return AssetJobStatus(
            job_id=job_id, status="COMPLETED", progress_percent=100
        )

    async def download_video(
        self, job_id: str, target_dir: str, ctx: ProviderCallContext
    ) -> GeneratedAsset:
        """Download video."""
        return GeneratedAsset(
            asset_id=f"vid_{uuid.uuid4()}",
            uri="/tmp/video.mp4",
            sha256="abc123",
            width=1280,
            height=720,
            duration_sec=5,
            format="mp4",
        )


