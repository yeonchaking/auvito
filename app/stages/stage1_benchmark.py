"""Stage 1: Benchmark and research."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from app.domain.contracts import BenchmarkReport
from app.domain.enums import ProjectStatus
from app.domain.models import Project, StageRun
from app.domain.schemas import BenchmarkRequest
from app.providers.research import YouTubeResearchProvider
from app.providers.base import ProviderCallContext
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.storage.sqlite import Database
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BenchmarkStageInput:
    """Input data for benchmark stage."""

    def __init__(
        self,
        project: Project,
        search_keywords: list[str],
        workspace_root: str,
        youtube_api_key: str,
        anthropic_api_key: Optional[str] = None,
    ):
        """Initialize benchmark stage input.

        Args:
            project: Project instance
            search_keywords: Keywords to search
            workspace_root: Workspace root directory
            youtube_api_key: YouTube Data API key
            anthropic_api_key: Optional Anthropic API key
        """
        self.project = project
        self.search_keywords = search_keywords
        self.workspace_root = workspace_root
        self.youtube_api_key = youtube_api_key
        self.anthropic_api_key = anthropic_api_key


class BenchmarkStage(BaseStage):
    """Stage 1: YouTube benchmark analysis.

    Analyzes competitor videos to extract patterns, hooks, CTR strategies,
    and content structure recommendations.
    """

    stage_name = "benchmark"

    def __init__(self, db: Database):
        """Initialize benchmark stage.

        Args:
            db: Database connection
        """
        self.db = db

    async def execute(self, input_data: BenchmarkStageInput) -> BenchmarkReport:
        """Perform benchmark analysis.

        Creates:
        - benchmark_report.json (BenchmarkReport contract)
        - benchmark_report.md (human-readable markdown)
        - keyword_bank.json (structured keyword suggestions)

        Args:
            input_data: Benchmark stage input

        Returns:
            BenchmarkReport contract

        Raises:
            ValueError: If benchmark analysis fails
        """
        project = input_data.project
        workspace = Path(input_data.workspace_root) / "projects" / project.slug
        benchmark_dir = workspace / "01_benchmark"

        logger.info(
            "Starting benchmark analysis",
            project_slug=project.slug,
            keyword_count=len(input_data.search_keywords),
        )

        # Create research provider
        research_provider = YouTubeResearchProvider(
            api_key=input_data.youtube_api_key,
            anthropic_api_key=input_data.anthropic_api_key,
        )

        # Build benchmark request
        benchmark_request = BenchmarkRequest(
            topic=project.title_seed,
            niche=project.niche,
            search_keywords=input_data.search_keywords,
            max_videos=10,
        )

        # Create provider context
        ctx = ProviderCallContext(
            run_id=str(project.id),
            stage_run_id=f"stg_{project.id}_{self.stage_name}_1",
            attempt_no=1,
            idempotency_key=self._compute_idempotency_key(
                project.id, input_data.search_keywords
            ),
        )

        try:
            # Estimate cost
            cost_estimate = await research_provider.estimate_cost(benchmark_request, ctx)
            logger.info(
                "Benchmark cost estimated",
                estimated_cost=cost_estimate.estimated_cost_usd,
            )

            # Perform benchmark
            report = await research_provider.benchmark(benchmark_request, ctx)

            # Save report as JSON
            report_json_path = benchmark_dir / "benchmark_report.json"
            await FileStorage.save_json(
                str(report_json_path), json.loads(report.model_dump_json())
            )

            # Convert to markdown for human review
            markdown_content = self._format_report_markdown(report)
            report_md_path = benchmark_dir / "benchmark_report.md"
            await FileStorage.save_text(str(report_md_path), markdown_content)

            # Save keyword bank
            keyword_bank = {
                "primary_keywords": report.keyword_bank.get("primary_keywords", []),
                "secondary_keywords": report.keyword_bank.get(
                    "secondary_keywords", []
                ),
                "long_tail_keywords": self._extract_long_tail_keywords(report),
                "seasonal_trends": report.keyword_bank.get("seasonal_trends", {}),
                "created_at": datetime.utcnow().isoformat(),
            }
            keyword_bank_path = benchmark_dir / "keyword_bank.json"
            await FileStorage.save_json(str(keyword_bank_path), keyword_bank)

            # Save LLM calls provenance
            await self._save_provenance(
                benchmark_dir, benchmark_request, report, cost_estimate
            )

            logger.info(
                "Benchmark analysis completed",
                project_slug=project.slug,
                videos_analyzed=report.analyzed_video_count,
            )

            return report

        except Exception as e:
            logger.error(
                "Benchmark analysis failed",
                project_slug=project.slug,
                error=str(e),
            )
            raise

    def _compute_idempotency_key(
        self, project_id: Any, keywords: list[str]
    ) -> str:
        """Compute idempotency key for benchmark execution.

        Args:
            project_id: Project ID
            keywords: Search keywords

        Returns:
            Idempotency key hash
        """
        content = f"{project_id}:{','.join(keywords)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _format_report_markdown(self, report: BenchmarkReport) -> str:
        """Format benchmark report as markdown.

        Args:
            report: BenchmarkReport contract

        Returns:
            Markdown formatted report
        """
        md_lines = [
            "# Benchmark Analysis Report",
            "",
            f"**Niche**: {report.niche}",
            f"**Videos Analyzed**: {report.analyzed_video_count}",
            f"**Analysis Period**: {report.analysis_period_days} days",
            f"**Confidence Level**: {report.analysis_confidence}",
            "",
            "## Top Patterns",
            "",
        ]

        if report.top_patterns:
            for key, value in report.top_patterns.items():
                md_lines.append(f"### {key.replace('_', ' ').title()}")
                if isinstance(value, dict):
                    for k, v in value.items():
                        md_lines.append(f"- **{k}**: {v}")
                elif isinstance(value, list):
                    for item in value:
                        md_lines.append(f"- {item}")
                else:
                    md_lines.append(f"- {value}")
                md_lines.append("")

        md_lines.extend(
            [
                "## Keyword Bank",
                "",
            ]
        )

        if report.keyword_bank:
            for key, value in report.keyword_bank.items():
                md_lines.append(f"### {key.replace('_', ' ').title()}")
                if isinstance(value, list):
                    for item in value:
                        md_lines.append(f"- {item}")
                md_lines.append("")

        md_lines.extend(
            [
                "## Competitor Analysis",
                "",
            ]
        )

        if report.competitor_analysis:
            if "top_performers" in report.competitor_analysis:
                md_lines.append("### Top Performing Videos")
                for video in report.competitor_analysis.get("top_performers", []):
                    if isinstance(video, dict):
                        md_lines.append(f"- **{video.get('title', 'N/A')}**")
                        md_lines.append(
                            f"  - Views: {video.get('views', 'N/A'):,}"
                        )
                        md_lines.append(
                            f"  - Engagement Rate: {video.get('engagement_rate', 0):.2%}"
                        )
                md_lines.append("")

        md_lines.extend(
            [
                "## CTR & Engagement Insights",
                "",
            ]
        )

        if report.ctr_insights:
            for key, value in report.ctr_insights.items():
                md_lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")

        md_lines.extend(
            [
                "",
                "---",
                f"*Generated: {report.created_at.isoformat()}*",
            ]
        )

        return "\n".join(md_lines)

    def _extract_long_tail_keywords(self, report: BenchmarkReport) -> list[str]:
        """Extract long-tail keywords from report patterns.

        Args:
            report: BenchmarkReport contract

        Returns:
            List of long-tail keywords
        """
        long_tail = []

        # Extract from top patterns
        if report.top_patterns:
            patterns = report.top_patterns.get("common_title_elements", [])
            for pattern in patterns:
                if isinstance(pattern, str) and len(pattern.split()) > 1:
                    long_tail.append(pattern)

        return long_tail[:10]

    async def _save_provenance(
        self,
        benchmark_dir: Path,
        request: BenchmarkRequest,
        report: BenchmarkReport,
        cost_estimate: Any,
    ) -> None:
        """Save provenance information for LLM calls.

        Args:
            benchmark_dir: Benchmark directory
            request: Original request
            report: Generated report
            cost_estimate: Cost estimate
        """
        provenance = {
            "stage": "benchmark",
            "timestamp": datetime.utcnow().isoformat(),
            "request": {
                "topic": request.topic,
                "niche": request.niche,
                "search_keywords": request.search_keywords,
                "max_videos": request.max_videos,
            },
            "cost_estimate": {
                "estimated_usd": str(cost_estimate.estimated_cost_usd),
                "confidence": cost_estimate.confidence,
                "reasoning": cost_estimate.reasoning,
            },
            "output": {
                "contract_type": report.contract_type,
                "schema_version": report.schema_version,
                "analyzed_video_count": report.analyzed_video_count,
                "analysis_confidence": report.analysis_confidence,
            },
        }

        provenance_path = benchmark_dir / "provenance.json"
        await FileStorage.save_json(str(provenance_path), provenance)
