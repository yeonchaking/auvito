"""HITL approval service."""

from typing import Optional
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from app.domain.models import Approval
from app.domain.enums import ApprovalStatus
from app.storage.sqlite import Database


class ApprovalService:
    """Service for managing human approvals."""

    def __init__(self, db: Database):
        """Initialize approval service."""
        self.db = db

    async def create_approval(
        self,
        run_id: str,
        checkpoint_name: str,
        entity_type: str,
        entity_ref: str,
        estimated_cost_usd: Decimal,
        summary: str,
        diff_ref: Optional[str] = None,
    ) -> Approval:
        """Create an approval request."""
        approval = Approval(
            approval_id=f"apr_{uuid4()}",
            run_id=run_id,
            checkpoint_name=checkpoint_name,
            entity_type=entity_type,
            entity_ref=entity_ref,
            status=ApprovalStatus.PENDING,
            estimated_incremental_cost_usd=estimated_cost_usd,
            summary=summary,
            diff_ref=diff_ref,
            created_at=datetime.utcnow(),
        )
        await self.db.save_approval(approval)
        return approval

    async def get_approval(self, approval_id: str) -> Optional[Approval]:
        """Get approval by ID."""
        return await self.db.get_approval(approval_id)

    async def approve(
        self, approval_id: str, reviewer: str, comment: Optional[str] = None
    ) -> bool:
        """Approve a request."""
        approval = await self.get_approval(approval_id)
        if not approval:
            return False

        approval.status = ApprovalStatus.APPROVED
        approval.reviewer = reviewer
        approval.decision_comment = comment
        approval.resolved_at = datetime.utcnow()

        return await self.db.save_approval(approval)

    async def reject(
        self, approval_id: str, reviewer: str, reason: str
    ) -> bool:
        """Reject a request."""
        approval = await self.get_approval(approval_id)
        if not approval:
            return False

        approval.status = ApprovalStatus.REJECTED
        approval.reviewer = reviewer
        approval.decision_comment = reason
        approval.resolved_at = datetime.utcnow()

        return await self.db.save_approval(approval)

    async def list_pending(self, run_id: str) -> list[Approval]:
        """List pending approvals for a run."""
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM approvals WHERE run_id = ? AND status = 'PENDING' ORDER BY created_at DESC",
                (run_id,),
            )
            rows = await cursor.fetchall()
            return [Approval(**dict(row)) for row in rows]
        except Exception:
            return []

    async def list_all_pending(self) -> list[Approval]:
        """List all pending approvals."""
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM approvals WHERE status = 'PENDING' ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            return [Approval(**dict(row)) for row in rows]
        except Exception:
            return []

    async def get_latest_for_checkpoint(
        self, run_id: str, checkpoint_name: str
    ) -> Optional[Approval]:
        """Get the latest approval record for a run/checkpoint pair."""
        try:
            cursor = await self.db.connection.execute(
                """
                SELECT * FROM approvals
                WHERE run_id = ? AND checkpoint_name = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id, checkpoint_name),
            )
            row = await cursor.fetchone()
            if row:
                return Approval(**dict(row))
        except Exception:
            pass
        return None
