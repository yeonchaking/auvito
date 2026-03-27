"""Tests for cost guardrail."""

from decimal import Decimal

import pytest

from app.core.cost_guardrail import CostGuardrail
from app.domain.enums import FailureClass


@pytest.fixture
def guardrail():
    """Create guardrail instance."""
    config = {
        "estimation": {"unknown_price": "fail", "pessimistic_multiplier": 1.25},
        "budgets": {
            "run_soft_cap_usd": 10.00,
            "run_hard_cap_usd": 15.00,
        },
        "per_stage": {
            "script": {"hard_cap_usd": 0.80},
            "assets": {"hard_cap_usd": 8.00},
        },
        "provider_limits": {"openai": {"monthly_cap_usd": 100.00}},
        "actions": {"on_hard_cap": "fail"},
    }
    return CostGuardrail(config)


def test_preflight_check_ok(guardrail):
    """Test preflight check passes when under cap."""
    result = guardrail.check_preflight(
        "run_123",
        "script",
        Decimal("0.50"),
        Decimal("0.00"),
        Decimal("0.00"),
    )
    assert result is None


def test_preflight_check_stage_cap_exceeded(guardrail):
    """Test preflight check fails when stage cap exceeded."""
    result = guardrail.check_preflight(
        "run_123",
        "script",
        Decimal("1.00"),  # Exceeds script cap of 0.80
        Decimal("0.00"),
        Decimal("0.00"),
    )
    assert result is not None
    assert "stage cap" in result.lower()


def test_preflight_check_run_cap_exceeded(guardrail):
    """Test preflight check fails when run cap exceeded."""
    result = guardrail.check_preflight(
        "run_123",
        "assets",
        Decimal("8.00"),
        Decimal("7.50"),  # Already spent 7.50
        Decimal("0.00"),
    )
    assert result is not None
    assert "run cap" in result.lower()


def test_classify_failure():
    """Test failure classification."""
    guardrail = CostGuardrail({})

    assert (
        guardrail.classify_failure(Exception("429 rate limit"))
        == FailureClass.TRANSIENT_PROVIDER
    )
    assert (
        guardrail.classify_failure(Exception("timeout")) == FailureClass.ASYNC_JOB_TIMEOUT
    )


def test_should_retry():
    """Test retry decision logic."""
    guardrail = CostGuardrail({})

    assert guardrail.should_retry(FailureClass.TRANSIENT_PROVIDER) is True
    assert guardrail.should_retry(FailureClass.LOCAL_TOOL_TRANSIENT) is True
    assert guardrail.should_retry(FailureClass.INVALID_INPUT) is False
