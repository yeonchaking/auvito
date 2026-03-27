"""Research provider abstraction and implementations."""

from typing import Any, Optional, Protocol

from pydantic import BaseModel

from app.domain.contracts import BenchmarkReport
from app.domain.schemas import BenchmarkRequest
from app.providers.base import CostEstimate, ProviderCallContext


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
