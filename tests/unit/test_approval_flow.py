"""Approval flow regression tests."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.domain.enums import ApprovalStatus, ProjectStatus
from app.domain.models import Approval, Project
from app.storage.sqlite import Database


def _make_db_path() -> Path:
    workspace_dir = Path.cwd() / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir / f"test_{uuid4().hex}.db"


@pytest.mark.asyncio
async def test_orchestrator_creates_and_honors_stage_approval(monkeypatch):
    db_path = _make_db_path()
    db = Database(str(db_path))
    try:
        await db.init()

        project = Project(
            id=uuid4(),
            slug="demo-project",
            title_seed="Demo Project",
            channel_name="Demo Channel",
            niche="Demo",
            status=ProjectStatus.CREATED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        assert await db.save_project(project) is True

        orchestrator = PipelineOrchestrator(db, cost_guardrail=None, config={}, settings=None)

        executed_stages = []

        monkeypatch.setattr(orchestrator, "_get_workspace_root", lambda: str(db_path.parent))
        monkeypatch.setattr(orchestrator, "_create_providers", lambda: {})

        async def fake_execute_stage(**kwargs):
            executed_stages.append(kwargs["stage_name"])
            return {"success": True, "result": f"{kwargs['stage_name']} done"}

        monkeypatch.setattr(orchestrator, "_execute_stage", fake_execute_stage)

        first_result = await orchestrator.run_pipeline(
            slug=project.slug,
            from_stage="script",
            until_stage="script",
            run_id="run_demo123",
        )

        assert first_result["completed"] is False
        assert first_result["stages"]["script"]["status"] == "awaiting_approval"
        approval_id = first_result["stages"]["script"]["approval_id"]
        pending = await orchestrator.approvals.list_pending("run_demo123")
        assert [approval.approval_id for approval in pending] == [approval_id]
        assert executed_stages == []

        approved = await orchestrator.approvals.approve(
            approval_id, reviewer="tester", comment="looks good"
        )
        assert approved is True

        second_result = await orchestrator.run_pipeline(
            slug=project.slug,
            from_stage="script",
            until_stage="script",
            run_id="run_demo123",
        )

        assert second_result["completed"] is True
        assert second_result["stages"]["script"]["success"] is True
        assert executed_stages == ["script"]

        latest_approval = await orchestrator.approvals.get_latest_for_checkpoint(
            "run_demo123", "script"
        )
        assert latest_approval is not None
        assert latest_approval.status == ApprovalStatus.APPROVED

    finally:
        if db.connection:
            await db.close()
        if db_path.exists():
            db_path.unlink()


@pytest.mark.asyncio
async def test_approval_service_lists_all_pending():
    db_path = _make_db_path()
    db = Database(str(db_path))
    try:
        await db.init()

        first = Approval(
            approval_id="apr_pending",
            run_id="run_one",
            checkpoint_name="script",
            entity_type="stage",
            entity_ref="demo-project:script",
            status=ApprovalStatus.PENDING,
            estimated_incremental_cost_usd=Decimal("0.00"),
            summary="pending",
            created_at=datetime.utcnow(),
        )
        second = Approval(
            approval_id="apr_done",
            run_id="run_two",
            checkpoint_name="storyboard",
            entity_type="stage",
            entity_ref="demo-project:storyboard",
            status=ApprovalStatus.APPROVED,
            estimated_incremental_cost_usd=Decimal("0.00"),
            summary="approved",
            reviewer="tester",
            created_at=datetime.utcnow(),
            resolved_at=datetime.utcnow(),
        )

        assert await db.save_approval(first) is True
        assert await db.save_approval(second) is True

        approvals = await PipelineOrchestrator(
            db, cost_guardrail=None, config={}, settings=None
        ).approvals.list_all_pending()

        assert [approval.approval_id for approval in approvals] == ["apr_pending"]

    finally:
        if db.connection:
            await db.close()
        if db_path.exists():
            db_path.unlink()
