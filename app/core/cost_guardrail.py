"""Cost guardrail and budget management."""

from decimal import Decimal
from typing import Optional
from app.domain.enums import FailureClass


class CostGuardrail:
    """Cost policy enforcement engine."""

    def __init__(self, config: dict):
        """Initialize cost guardrail."""
        self.config = config
        self.estimation = config.get("estimation", {})
        self.budgets = config.get("budgets", {})
        self.per_stage = config.get("per_stage", {})
        self.provider_limits = config.get("provider_limits", {})
        self.actions = config.get("actions", {})

    def check_preflight(
        self,
        run_id: str,
        stage_name: str,
        estimated_cost_usd: Decimal,
        current_actual_usd: Decimal,
        current_reserved_usd: Decimal,
    ) -> Optional[str]:
        """
        Check cost before stage starts.

        Returns error message if cost exceeds hard cap, None if OK.
        """
        # Stage-specific hard cap
        stage_config = self.per_stage.get(stage_name, {})
        stage_hard_cap = Decimal(stage_config.get("hard_cap_usd", "999999"))

        # Run-wide hard cap
        run_hard_cap = Decimal(self.budgets.get("run_hard_cap_usd", "15.00"))

        # Check stage cap
        if estimated_cost_usd > stage_hard_cap:
            return f"Estimated cost {estimated_cost_usd} exceeds stage cap {stage_hard_cap}"

        # Check run cap (accumulated)
        total_projected = current_actual_usd + current_reserved_usd + estimated_cost_usd
        if total_projected > run_hard_cap:
            return f"Projected total cost {total_projected} exceeds run cap {run_hard_cap}"

        return None

    def check_provider_call(
        self,
        provider: str,
        model: str,
        estimated_cost_usd: Decimal,
        current_run_cost_usd: Decimal,
    ) -> Optional[str]:
        """
        Check provider-specific limits before call.

        Returns error message if limits exceeded, None if OK.
        """
        provider_config = self.provider_limits.get(provider, {})
        monthly_cap = Decimal(provider_config.get("monthly_cap_usd", "999999"))

        # Check monthly cap
        if current_run_cost_usd > monthly_cap:
            return f"Provider {provider} monthly cap {monthly_cap} exceeded"

        return None

    def classify_failure(self, error: Exception) -> FailureClass:
        """Classify failure for retry logic."""
        error_str = str(error).lower()

        if "429" in error_str or "rate limit" in error_str:
            return FailureClass.TRANSIENT_PROVIDER
        elif "timeout" in error_str or "deadline" in error_str:
            return FailureClass.ASYNC_JOB_TIMEOUT
        elif "invalid" in error_str or "schema" in error_str:
            return FailureClass.INVALID_INPUT
        elif "json" in error_str or "parse" in error_str:
            return FailureClass.INVALID_OUTPUT
        elif "permission denied" in error_str or "file" in error_str:
            return FailureClass.LOCAL_TOOL_TRANSIENT
        elif "ffmpeg" in error_str or "codec" in error_str:
            return FailureClass.LOCAL_TOOL_FATAL

        return FailureClass.TRANSIENT_PROVIDER

    def should_retry(self, failure_class: FailureClass) -> bool:
        """Determine if failure should trigger retry."""
        retryable = {
            FailureClass.TRANSIENT_PROVIDER,
            FailureClass.LOCAL_TOOL_TRANSIENT,
        }
        return failure_class in retryable
