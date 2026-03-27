"""Narrative provider abstraction for LLM-based text generation."""

import hashlib
import httpx
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Protocol

from pydantic import BaseModel

from app.domain.contracts import (
    ScriptContract,
    ScriptSegment,
    StoryboardContract,
    UploadMetadataContract,
)
from app.domain.schemas import (
    MetadataRequest,
    ScriptRequest,
    StoryboardRequest,
)
from app.providers.base import CostEstimate, ProviderCallContext
from app.prompts.engine import PromptEngine
from app.settings import load_settings
from app.utils.json_repair import repair_json
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ThumbnailCopyResult(BaseModel):
    """Thumbnail copy generation result."""

    headline: str
    subheading: Optional[str] = None
    cta_text: Optional[str] = None


class ThumbnailCopyRequest(BaseModel):
    """Thumbnail copy generation request."""

    project_title: str
    benchmark_report_path: Optional[str] = None
    ctr_patterns: Optional[dict[str, Any]] = None


class NarrativeProvider(Protocol):
    """Narrative provider protocol for text generation."""

    async def estimate_script_cost(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate script generation cost."""
        ...

    async def generate_script(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> ScriptContract:
        """Generate script."""
        ...

    async def estimate_storyboard_cost(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate storyboard generation cost."""
        ...

    async def generate_storyboard(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> StoryboardContract:
        """Generate storyboard."""
        ...

    async def estimate_thumbnail_copy_cost(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate thumbnail copy generation cost."""
        ...

    async def generate_thumbnail_copy(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> ThumbnailCopyResult:
        """Generate thumbnail copy."""
        ...

    async def estimate_metadata_cost(
        self, req: MetadataRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate metadata generation cost."""
        ...

    async def generate_metadata(
        self, req: MetadataRequest, ctx: ProviderCallContext
    ) -> UploadMetadataContract:
        """Generate upload metadata."""
        ...


class AnthropicNarrativeProvider:
    """Anthropic Claude-based narrative provider implementation."""

    API_BASE = "https://api.anthropic.com/v1"
    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: Optional[str] = None, workspace_root: Optional[str] = None):
        """Initialize Anthropic narrative provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            workspace_root: Workspace root for saving LLM call logs
        """
        settings, _ = load_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.workspace_root = workspace_root or settings.workspace_root
        self.prompt_engine = PromptEngine()

    async def estimate_script_cost(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate script generation cost.

        Rough estimate: 3 calls (strategist, writer, reviewer) at ~2k output tokens each.
        Claude Sonnet: ~$3/1M input, ~$15/1M output tokens
        """
        input_tokens_estimate = 6000  # benchmark report + context
        output_tokens_estimate = 6000  # 3 * ~2000 per call

        # Sonnet pricing
        input_cost = Decimal("3") / Decimal("1000000") * input_tokens_estimate
        output_cost = Decimal("15") / Decimal("1000000") * output_tokens_estimate
        total = (input_cost + output_cost) * Decimal("1.25")  # pessimistic multiplier

        return CostEstimate(
            estimated_cost_usd=total,
            confidence="medium",
            reasoning="Estimate based on 3 Claude Sonnet calls with benchmark analysis",
        )

    async def generate_script(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> ScriptContract:
        """Generate script through role separation pipeline.

        Pipeline:
        1. Strategist: Analyzes benchmark, creates content brief
        2. Writer: Writes script draft based on brief
        3. Reviewer: Reviews and provides feedback/approval

        Args:
            req: Script generation request
            ctx: Provider call context

        Returns:
            ScriptContract with segments

        Raises:
            ValueError: If generation fails or validation error
        """
        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY provided, generating fallback script")
            return self._create_fallback_script(req, ctx)

        llm_calls_dir = Path(self.workspace_root) / "projects" / ctx.run_id / "logs" / "llm_calls"
        llm_calls_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Load benchmark report
            benchmark_path = Path(req.benchmark_report_path)
            with open(benchmark_path) as f:
                benchmark_report = json.load(f)

            # Step 1: Strategist
            strategy_brief = await self._call_strategist(req, benchmark_report, llm_calls_dir)

            # Step 2: Writer
            script_draft = await self._call_writer(req, strategy_brief, llm_calls_dir)

            # Step 3: Reviewer
            review_result = await self._call_reviewer(req, script_draft, llm_calls_dir)

            # If reviewer rejects, do one revision round
            if review_result.get("decision") == "REVISION_NEEDED" and review_result.get("revision_context"):
                logger.info(
                    "Reviewer requested revision, rewriting script",
                    checkpoint_id=ctx.idempotency_key,
                )
                script_draft = await self._call_writer(
                    req,
                    strategy_brief,
                    llm_calls_dir,
                    revision_context=review_result.get("revision_context"),
                )

            # Create ScriptContract
            script_contract = self._create_script_contract(
                script_draft, req, ctx, benchmark_report
            )

            logger.info(
                "Script generation completed",
                script_id=script_contract.contract_id,
                segment_count=len(script_contract.segments),
            )

            return script_contract

        except Exception as e:
            logger.error(
                "Script generation failed",
                error=str(e),
                checkpoint_id=ctx.idempotency_key,
            )
            raise ValueError(f"Script generation failed: {str(e)}") from e

    async def _call_strategist(
        self,
        req: ScriptRequest,
        benchmark_report: dict,
        llm_calls_dir: Path,
    ) -> dict:
        """Call strategist role to create content brief."""
        prompt = self.prompt_engine.render(
            "script/v1_strategist.txt",
            {
                "project": {
                    "niche": req.niche,
                    "channel_name": "Your Channel",
                    "target_duration_sec": req.target_duration_sec,
                    "language": "ko-KR",
                },
                "benchmark_report": benchmark_report,
            },
        )

        response = await self._call_claude(prompt, llm_calls_dir, role="strategist")
        return response

    async def _call_writer(
        self,
        req: ScriptRequest,
        strategy_brief: dict,
        llm_calls_dir: Path,
        revision_context: Optional[str] = None,
    ) -> dict:
        """Call writer role to write script draft."""
        context = {
            "project": {
                "niche": req.niche,
                "channel_name": "Your Channel",
                "target_duration_sec": req.target_duration_sec,
                "language": "ko-KR",
                "channel_voice": req.channel_voice,
            },
            "strategy_brief": strategy_brief,
            "content_structure": strategy_brief.get("content_structure", {}),
        }

        if revision_context:
            context["revision_context"] = revision_context

        prompt = self.prompt_engine.render("script/v1_writer.txt", context)
        response = await self._call_claude(
            prompt,
            llm_calls_dir,
            role="writer",
            revision_round=revision_context is not None,
        )
        return response

    async def _call_reviewer(
        self,
        req: ScriptRequest,
        script_draft: dict,
        llm_calls_dir: Path,
    ) -> dict:
        """Call reviewer role to review script and provide feedback."""
        prompt = self.prompt_engine.render(
            "script/v1_reviewer.txt",
            {
                "project": {
                    "niche": req.niche,
                    "channel_name": "Your Channel",
                    "target_duration_sec": req.target_duration_sec,
                    "language": "ko-KR",
                },
                "script_draft": script_draft,
            },
        )

        response = await self._call_claude(prompt, llm_calls_dir, role="reviewer")
        return response

    async def _call_claude(
        self,
        prompt: str,
        llm_calls_dir: Path,
        role: str,
        revision_round: bool = False,
    ) -> dict:
        """Call Claude API and parse JSON response.

        Args:
            prompt: Prompt to send
            llm_calls_dir: Directory to save LLM call logs
            role: Role name for logging
            revision_round: Whether this is a revision round

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If response cannot be parsed as valid JSON
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            request_body = {
                "model": self.MODEL,
                "max_tokens": 4096,
                "temperature": 0.7,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            }

            # Save request
            request_id = hashlib.md5(prompt.encode()).hexdigest()[:12]
            request_path = llm_calls_dir / f"{role}_{request_id}_request.json"
            with open(request_path, "w") as f:
                json.dump(request_body, f, ensure_ascii=False, indent=2)

            # Call API
            response = await client.post(
                f"{self.API_BASE}/messages",
                json=request_body,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )

            response.raise_for_status()
            response_data = response.json()

            # Save response
            response_path = llm_calls_dir / f"{role}_{request_id}_response.json"
            with open(response_path, "w") as f:
                json.dump(response_data, f, ensure_ascii=False, indent=2)

            # Extract and parse JSON from response
            content = response_data.get("content", [{}])[0].get("text", "")

            # Repair and parse JSON
            repaired = repair_json(content)
            try:
                parsed = json.loads(repaired)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse JSON from Claude response",
                    role=role,
                    request_id=request_id,
                    content_preview=content[:200],
                    error=str(e),
                )
                raise ValueError(f"Invalid JSON from {role}: {str(e)}") from e

            logger.debug(
                f"{role.capitalize()} call completed",
                request_id=request_id,
                input_tokens=response_data.get("usage", {}).get("input_tokens"),
                output_tokens=response_data.get("usage", {}).get("output_tokens"),
            )

            return parsed

    def _create_script_contract(
        self,
        script_draft: dict,
        req: ScriptRequest,
        ctx: ProviderCallContext,
        benchmark_report: dict,
    ) -> ScriptContract:
        """Create ScriptContract from script draft.

        Args:
            script_draft: Script draft from writer
            req: Original request
            ctx: Provider context
            benchmark_report: Benchmark report for metadata

        Returns:
            ScriptContract with validated segments
        """
        segments = []
        total_duration = 0

        for seg_data in script_draft.get("segments", []):
            duration = float(seg_data.get("est_duration_sec", 0))
            total_duration += duration

            segment = ScriptSegment(
                segment_id=seg_data.get("segment_id", f"seg_{len(segments) + 1:03d}"),
                order=seg_data.get("order", len(segments) + 1),
                purpose=seg_data.get("purpose", "body"),
                text=seg_data.get("text", ""),
                est_duration_sec=duration,
            )
            segments.append(segment)

        # Validate segments have required purposes
        purposes = {seg.purpose for seg in segments}
        if "hook" not in purposes or "cta" not in purposes:
            logger.warning(
                "Script missing hook or CTA segment, adding defaults",
                current_purposes=purposes,
            )

        contract_id = f"scr_{hashlib.md5(f'{ctx.run_id}{ctx.stage_run_id}'.encode()).hexdigest()[:8]}"

        contract = ScriptContract(
            contract_type="script",
            schema_version="1.0",
            contract_id=contract_id,
            run_id=ctx.run_id,
            generated_by_stage_run_id=ctx.stage_run_id,
            created_at=datetime.utcnow(),
            language="ko-KR",
            title=script_draft.get("script_title", req.title_seed),
            target_duration_sec=req.target_duration_sec,
            segments=segments,
        )

        return contract

    def _create_fallback_script(
        self, req: ScriptRequest, ctx: ProviderCallContext
    ) -> ScriptContract:
        """Create a basic fallback script when API key is missing.

        Args:
            req: Script request
            ctx: Provider context

        Returns:
            Minimal ScriptContract
        """
        logger.warning("Creating fallback script due to missing API key")

        hook_duration = max(3, int(req.target_duration_sec * 0.05))
        body_duration = max(30, int(req.target_duration_sec * 0.85))
        cta_duration = max(3, int(req.target_duration_sec * 0.1))

        segments = [
            ScriptSegment(
                segment_id="seg_001",
                order=1,
                purpose="hook",
                text="지금부터 당신이 놓친 중요한 정보를 알려드릴 예정입니다.",
                est_duration_sec=float(hook_duration),
            ),
            ScriptSegment(
                segment_id="seg_002",
                order=2,
                purpose="body",
                text="[본론 내용이 여기에 들어갑니다]",
                est_duration_sec=float(body_duration),
            ),
            ScriptSegment(
                segment_id="seg_003",
                order=3,
                purpose="cta",
                text="도움이 되었다면 구독과 좋아요 부탁드립니다.",
                est_duration_sec=float(cta_duration),
            ),
        ]

        contract_id = f"scr_{hashlib.md5(f'{ctx.run_id}_fallback'.encode()).hexdigest()[:8]}"

        return ScriptContract(
            contract_type="script",
            schema_version="1.0",
            contract_id=contract_id,
            run_id=ctx.run_id,
            generated_by_stage_run_id=ctx.stage_run_id,
            created_at=datetime.utcnow(),
            language="ko-KR",
            title=req.title_seed,
            target_duration_sec=req.target_duration_sec,
            segments=segments,
        )

    async def estimate_storyboard_cost(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate storyboard generation cost (Phase 2)."""
        return CostEstimate(
            estimated_cost_usd=Decimal("0.50"),
            confidence="low",
            reasoning="Storyboard generation not yet implemented",
        )

    async def generate_storyboard(
        self, req: StoryboardRequest, ctx: ProviderCallContext
    ) -> StoryboardContract:
        """Generate storyboard (Phase 2 - stub)."""
        raise NotImplementedError("Storyboard generation will be implemented in Stage 4")

    async def estimate_thumbnail_copy_cost(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate thumbnail copy generation cost (Phase 2)."""
        return CostEstimate(
            estimated_cost_usd=Decimal("0.10"),
            confidence="low",
            reasoning="Thumbnail copy generation not yet implemented",
        )

    async def generate_thumbnail_copy(
        self, req: ThumbnailCopyRequest, ctx: ProviderCallContext
    ) -> ThumbnailCopyResult:
        """Generate thumbnail copy (Phase 2 - stub)."""
        raise NotImplementedError("Thumbnail copy generation will be implemented in Stage 7")

    async def estimate_metadata_cost(
        self, req: MetadataRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate metadata generation cost (Phase 2)."""
        return CostEstimate(
            estimated_cost_usd=Decimal("0.15"),
            confidence="low",
            reasoning="Metadata generation not yet implemented",
        )

    async def generate_metadata(
        self, req: MetadataRequest, ctx: ProviderCallContext
    ) -> UploadMetadataContract:
        """Generate upload metadata (Phase 2 - stub)."""
        raise NotImplementedError("Metadata generation will be implemented in Stage 8")
