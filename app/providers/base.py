"""Base provider abstractions."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel


@dataclass(frozen=True)
class ProviderCallContext:
    """Context for provider calls."""

    run_id: str
    stage_run_id: str
    attempt_no: int
    idempotency_key: str
    deadline_s: Optional[float] = None
    dry_run: bool = False


class CostEstimate(BaseModel):
    """Cost estimate from provider."""

    estimated_cost_usd: Decimal
    confidence: str = "medium"  # high | medium | low
    reasoning: Optional[str] = None


class ProviderMeta(BaseModel):
    """Metadata from provider response."""

    provider_name: str
    model: str
    request_id: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    actual_cost_usd: Optional[Decimal] = None
    metadata: dict[str, Any] = {}
