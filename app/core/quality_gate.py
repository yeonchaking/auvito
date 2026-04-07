"""Quality gate for automatic validation."""

from typing import Any, Literal
from pydantic import BaseModel


class GateResult(BaseModel):
    """Quality gate result."""

    gate_id: str
    stage_name: str
    severity: Literal["warn", "block"]
    passed: bool
    metrics: dict[str, Any] = {}
    message: str | None = None


class QualityGateRunner:
    """Runs automatic quality checks on stage outputs."""

    async def validate_script(self, script_contract: Any) -> GateResult:
        """Validate script contract."""
        passed = True
        issues = []

        # Check for empty segments
        if not script_contract.segments:
            passed = False
            issues.append("No segments defined")

        # Check segment ordering
        for i, segment in enumerate(script_contract.segments):
            if segment.order != i + 1:
                issues.append(f"Segment ordering invalid at {segment.segment_id}")

        message = "; ".join(issues) if issues else "Script validation passed"

        return GateResult(
            gate_id=f"gate_script_{script_contract.contract_id}",
            stage_name="script",
            severity="block" if not passed else "warn",
            passed=passed,
            metrics={"segment_count": len(script_contract.segments)},
            message=message,
        )

    async def validate_voice(self, narration_contract: Any) -> GateResult:
        """Validate narration contract."""
        passed = True
        issues = []

        # Check for clips
        if not narration_contract.clips:
            passed = False
            issues.append("No narration clips defined")

        # Check total duration
        total_duration = narration_contract.total_duration_sec
        if total_duration <= 0:
            passed = False
            issues.append("Invalid total duration")

        message = "; ".join(issues) if issues else "Voice validation passed"

        return GateResult(
            gate_id=f"gate_voice_{narration_contract.contract_id}",
            stage_name="voice",
            severity="block" if not passed else "warn",
            passed=passed,
            metrics={
                "clip_count": len(narration_contract.clips),
                "duration_sec": total_duration,
            },
            message=message,
        )

    async def validate_storyboard(self, storyboard_contract: Any) -> GateResult:
        """Validate storyboard contract."""
        passed = True
        issues = []

        if not storyboard_contract.shots:
            passed = False
            issues.append("No shots defined")

        # Check shot coverage
        total_duration = storyboard_contract.total_duration_sec
        covered_duration = sum(
            shot.end_sec - shot.start_sec for shot in storyboard_contract.shots
        )

        if covered_duration < total_duration * 0.95:
            issues.append(
                f"Shots cover {covered_duration}s but should cover {total_duration}s"
            )

        message = "; ".join(issues) if issues else "Storyboard validation passed"

        return GateResult(
            gate_id=f"gate_storyboard_{storyboard_contract.contract_id}",
            stage_name="storyboard",
            severity="block" if not passed else "warn",
            passed=passed,
            metrics={"shot_count": len(storyboard_contract.shots)},
            message=message,
        )

    async def validate_assets(self, asset_manifest: Any) -> GateResult:
        """Validate asset manifest."""
        passed = True
        issues = []

        if not asset_manifest.selected_assets:
            passed = False
            issues.append("No assets selected")

        message = "; ".join(issues) if issues else "Assets validation passed"

        return GateResult(
            gate_id=f"gate_assets_{asset_manifest.contract_id}",
            stage_name="assets",
            severity="block" if not passed else "warn",
            passed=passed,
            metrics={"asset_count": len(asset_manifest.selected_assets)},
            message=message,
        )

    async def validate_render(self, render_plan: Any) -> GateResult:
        """Validate render plan."""
        passed = True
        issues = []

        if not render_plan.timeline_items:
            passed = False
            issues.append("No timeline items")

        message = "; ".join(issues) if issues else "Render validation passed"

        return GateResult(
            gate_id=f"gate_render_{render_plan.contract_id}",
            stage_name="render",
            severity="block" if not passed else "warn",
            passed=passed,
            metrics={"timeline_items": len(render_plan.timeline_items)},
            message=message,
        )

