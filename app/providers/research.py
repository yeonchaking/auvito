"""Research provider abstraction and implementations."""

import hashlib
import httpx
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Protocol
from pathlib import Path

from pydantic import BaseModel

from app.domain.contracts import BenchmarkReport
from app.domain.schemas import BenchmarkRequest
from app.providers.base import CostEstimate, ProviderCallContext, ProviderMeta
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResearchResult(BaseModel):
    """Research result."""

    report: BenchmarkReport
    meta: dict[str, Any]


class ResearchProvider(Protocol):
    """Research provider protocol."""

    async def estimate_cost(
        self, req: BenchmarkRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost for benchmark."""
        ...

    async def benchmark(
        self, req: BenchmarkRequest, ctx: ProviderCallContext
    ) -> BenchmarkReport:
        """Generate benchmark report."""
        ...


class YouTubeResearchProvider:
    """YouTube Data API v3 research provider."""

    API_BASE = "https://www.googleapis.com/youtube/v3"
    QUOTA_UNIT_COST = 0.0001  # Rough estimate: 10,000 quota units per $1

    def __init__(self, api_key: str, anthropic_api_key: Optional[str] = None):
        """Initialize YouTube research provider.

        Args:
            api_key: YouTube Data API key
            anthropic_api_key: Optional Anthropic API key for LLM analysis
        """
        self.api_key = api_key
        self.anthropic_api_key = anthropic_api_key

    async def estimate_cost(
        self, req: BenchmarkRequest, ctx: ProviderCallContext
    ) -> CostEstimate:
        """Estimate cost for benchmark analysis.

        YouTube API pricing based on quota units:
        - search.list: 100 units per call
        - videos.list: 1 unit per video
        - commentThreads.list: 1 unit per comment

        Args:
            req: Benchmark request
            ctx: Provider call context

        Returns:
            Cost estimate
        """
        # Estimate quota units
        search_calls = len(req.search_keywords)  # Up to 5
        videos_per_search = 5  # Typical results per search
        total_videos = min(req.max_videos, search_calls * videos_per_search)
        comments_per_video = 20  # Top comments

        estimated_units = (
            (search_calls * 100)  # search.list calls
            + (total_videos * 1)  # videos.list calls
            + (total_videos * 10)  # commentThreads.list calls (10 units per call)
        )

        # Convert quota units to USD
        estimated_cost = Decimal(str(estimated_units * self.QUOTA_UNIT_COST))

        # Add LLM analysis cost if Anthropic key available
        if self.anthropic_api_key:
            estimated_cost += Decimal("0.10")  # Claude Sonnet analysis

        return CostEstimate(
            estimated_cost_usd=estimated_cost,
            confidence="medium",
            reasoning=f"Based on {estimated_units} YouTube quota units + optional LLM analysis",
        )

    async def benchmark(
        self, req: BenchmarkRequest, ctx: ProviderCallContext
    ) -> BenchmarkReport:
        """Perform YouTube benchmark analysis.

        Args:
            req: Benchmark request
            ctx: Provider call context

        Returns:
            Benchmark report

        Raises:
            ValueError: If API key missing or API errors occur
            httpx.HTTPError: If API calls fail
        """
        if not self.api_key:
            raise ValueError("YouTube API key required")

        # Collect competitor videos
        videos_data = await self._search_and_collect_videos(
            req.search_keywords, req.max_videos
        )

        if not videos_data:
            raise ValueError("No videos found for given keywords")

        # Extract patterns and prepare for LLM analysis
        analysis_payload = self._prepare_analysis_payload(
            videos_data, req.niche, req.search_keywords
        )

        # Analyze patterns (with LLM if available)
        patterns = await self._analyze_patterns(analysis_payload, ctx)

        # Create benchmark report
        report = BenchmarkReport(
            contract_type="benchmark_report",
            schema_version="1.0",
            contract_id=f"bench_{ctx.run_id[:8]}",
            run_id=ctx.run_id,
            generated_by_stage_run_id=ctx.stage_run_id,
            created_at=datetime.utcnow(),
            niche=req.niche,
            analyzed_video_count=len(videos_data),
            analysis_period_days=30,
            transcript_available=False,
            analysis_confidence="medium",
            top_patterns=patterns.get("top_patterns", {}),
            keyword_bank=patterns.get("keyword_bank", {}),
            competitor_analysis=patterns.get("competitor_analysis", {}),
            ctr_insights=patterns.get("ctr_insights", {}),
        )

        return report

    async def _search_and_collect_videos(
        self, keywords: list[str], max_videos: int
    ) -> list[dict[str, Any]]:
        """Search YouTube and collect video metadata.

        Args:
            keywords: Search keywords
            max_videos: Maximum videos to collect

        Returns:
            List of video data dictionaries
        """
        videos_data = []
        video_ids = set()

        async with httpx.AsyncClient() as client:
            for keyword in keywords[:5]:  # Max 5 searches
                if len(video_ids) >= max_videos:
                    break

                try:
                    # Search for videos
                    search_response = await client.get(
                        f"{self.API_BASE}/search",
                        params={
                            "key": self.api_key,
                            "part": "snippet",
                            "q": keyword,
                            "type": "video",
                            "maxResults": min(5, max_videos - len(video_ids)),
                            "relevanceLanguage": "ko",
                            "order": "viewCount",
                        },
                        timeout=10.0,
                    )
                    search_response.raise_for_status()
                    search_data = search_response.json()

                    # Extract video IDs
                    for item in search_data.get("items", []):
                        video_id = item["snippet"]["videoId"]
                        if video_id not in video_ids:
                            video_ids.add(video_id)

                except httpx.HTTPError as e:
                    logger.error(
                        "YouTube search failed",
                        keyword=keyword,
                        error=str(e),
                    )
                    continue

            # Get video statistics and details
            if video_ids:
                videos_data = await self._get_video_details(
                    list(video_ids)[:max_videos], client
                )

        return videos_data

    async def _get_video_details(
        self, video_ids: list[str], client: httpx.AsyncClient
    ) -> list[dict[str, Any]]:
        """Get detailed metadata for videos.

        Args:
            video_ids: List of video IDs
            client: HTTP client

        Returns:
            List of video detail dictionaries
        """
        videos_data = []

        try:
            response = await client.get(
                f"{self.API_BASE}/videos",
                params={
                    "key": self.api_key,
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(video_ids),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                video_info = {
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel_id": item["snippet"]["channelId"],
                    "published_at": item["snippet"]["publishedAt"],
                    "view_count": int(
                        item.get("statistics", {}).get("viewCount", 0)
                    ),
                    "like_count": int(
                        item.get("statistics", {}).get("likeCount", 0)
                    ),
                    "comment_count": int(
                        item.get("statistics", {}).get("commentCount", 0)
                    ),
                    "duration": item.get("contentDetails", {}).get("duration", ""),
                }
                videos_data.append(video_info)
        except httpx.HTTPError as e:
            logger.error("Failed to get video details", error=str(e))

        return videos_data

    def _prepare_analysis_payload(
        self, videos_data: list[dict[str, Any]], niche: str, keywords: list[str]
    ) -> dict[str, Any]:
        """Prepare data for LLM analysis.

        Args:
            videos_data: Video metadata
            niche: Content niche
            keywords: Search keywords

        Returns:
            Analysis payload
        """
        # Extract key metrics and patterns
        total_views = sum(v["view_count"] for v in videos_data)
        avg_views = total_views / len(videos_data) if videos_data else 0

        return {
            "niche": niche,
            "keywords": keywords,
            "video_count": len(videos_data),
            "videos": videos_data,
            "aggregate_metrics": {
                "total_views": total_views,
                "avg_views": avg_views,
                "avg_like_count": sum(v["like_count"] for v in videos_data)
                / len(videos_data)
                if videos_data
                else 0,
                "avg_comment_count": sum(v["comment_count"] for v in videos_data)
                / len(videos_data)
                if videos_data
                else 0,
            },
        }

    async def _analyze_patterns(
        self, payload: dict[str, Any], ctx: ProviderCallContext
    ) -> dict[str, Any]:
        """Analyze patterns in video data.

        With LLM if available, otherwise use basic heuristics.

        Args:
            payload: Analysis payload
            ctx: Provider call context

        Returns:
            Pattern analysis results
        """
        if self.anthropic_api_key:
            return await self._analyze_with_llm(payload, ctx)
        else:
            return self._analyze_with_heuristics(payload)

    async def _analyze_with_llm(
        self, payload: dict[str, Any], ctx: ProviderCallContext
    ) -> dict[str, Any]:
        """Analyze patterns using Anthropic Claude.

        Args:
            payload: Analysis payload
            ctx: Provider call context

        Returns:
            LLM analysis results
        """
        prompt = self._build_analysis_prompt(payload)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-opus-4-1",
                        "max_tokens": 2000,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                # Parse Claude's response
                content = result["content"][0]["text"]
                analysis = self._parse_llm_response(content)

                return analysis
        except Exception as e:
            logger.warning(
                "LLM analysis failed, falling back to heuristics",
                error=str(e),
            )
            return self._analyze_with_heuristics(payload)

    def _analyze_with_heuristics(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze patterns using heuristics.

        Args:
            payload: Analysis payload

        Returns:
            Heuristic analysis results
        """
        videos = payload["videos"]
        keywords = payload["keywords"]

        # Extract title patterns
        title_words = {}
        for video in videos:
            words = video["title"].split()
            for word in words:
                word = word.lower().strip("[]().,!?")
                if len(word) > 3:
                    title_words[word] = title_words.get(word, 0) + 1

        top_title_words = sorted(
            title_words.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "top_patterns": {
                "common_title_elements": [w[0] for w in top_title_words],
                "average_title_length": sum(
                    len(v["title"].split()) for v in videos
                )
                / len(videos)
                if videos
                else 0,
            },
            "keyword_bank": {
                "primary_keywords": keywords,
                "secondary_keywords": [w[0] for w in top_title_words[:5]],
            },
            "competitor_analysis": {
                "video_count": len(videos),
                "top_performers": [
                    {
                        "title": v["title"],
                        "views": v["view_count"],
                        "engagement_rate": (
                            (v["like_count"] + v["comment_count"])
                            / max(v["view_count"], 1)
                        ),
                    }
                    for v in sorted(videos, key=lambda x: x["view_count"], reverse=True)[
                        :3
                    ]
                ],
            },
            "ctr_insights": {
                "recommendation": "Focus on strong hooks and clear value props in titles",
                "confidence": "low",
            },
        }

    def _build_analysis_prompt(self, payload: dict[str, Any]) -> str:
        """Build analysis prompt for Claude.

        Args:
            payload: Analysis payload

        Returns:
            Formatted prompt
        """
        videos_summary = "\n".join(
            [
                f"- {v['title']} ({v['view_count']} views, {v['like_count']} likes, {v['comment_count']} comments)"
                for v in payload["videos"][:10]
            ]
        )

        return f"""Analyze these top YouTube videos in the '{payload['niche']}' niche for content patterns:

Videos analyzed:
{videos_summary}

Search keywords used: {', '.join(payload['keywords'])}

Provide analysis in JSON format with these keys:
1. top_patterns: Common structural and thematic patterns
2. keyword_bank: Recommended primary and secondary keywords
3. competitor_analysis: Top performer characteristics
4. ctr_insights: Title and thumbnail strategies

Return ONLY valid JSON, no markdown or explanation."""

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        """Parse LLM response JSON.

        Args:
            content: LLM response text

        Returns:
            Parsed analysis dictionary
        """
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                json_str = content[start:end].strip()
            else:
                json_str = content

            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return {
                "top_patterns": {},
                "keyword_bank": {},
                "competitor_analysis": {},
                "ctr_insights": {},
            }
