"""Stage execution logic with resume/skip/overwrite modes."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from app.domain.models import StageRun
from app.domain.enums import StageStatus
from app.storage.sqlite import Database


def calculate_execution_digest(
    input_digest: str,
    stage_impl_version: str,
    effective_config_digest: str,
    provider_digest: str,
    prompt_bundle_digest: str,
    output_schema_major: str,
) -> str:
    """Calculate execution digest from components."""
    components = {
        "input_digest": input_digest,
        "stage_impl_version": stage_impl_version,
        "effective_config_digest": effective_config_digest,
        "provider_digest": provider_digest,
        "prompt_bundle_digest": prompt_bundle_digest,
        "output_schema_major": output_schema_major,
    }
    canonical_json = json.dumps(components, sort_keys=True)
    return hashlib.sha256(canonical_json.encode()).hexdigest()


class StageExecutor:
    """Executes stages with support for skip/resume/overwrite modes."""

    def __init__(self, db: Database):
        """Initialize executor."""
        self.db = db

    async def decide_execution_mode(
        self,
        run_id: str,
        stage_name: str,
        requested_mode: Literal["skip", "resume", "overwrite"],
        execution_digest: str,
    ) -> tuple[Literal["execute", "skip", "resume"], Optional[str]]:
        """
        Decide whether to execute, skip, or resume a stage.

        Returns (decision, reference_stage_run_id).
        """
        # Find previous runs with same digest
        previous_runs = await self._find_previous_runs(
            run_id, stage_name, execution_digest
        )

        if requested_mode == "skip":
            if previous_runs and previous_runs[0].status == StageStatus.SUCCEEDED:
                return ("skip", previous_runs[0].stage_run_id)
            else:
                raise ValueError("No successful previous run to skip with")

        elif requested_mode == "resume":
            if previous_runs and previous_runs[0].status == StageStatus.SUCCEEDED:
                return ("skip", previous_runs[0].stage_run_id)
            elif (
                previous_runs
                and previous_runs[0].status == StageStatus.PARTIAL
                and previous_runs[0].resumable
            ):
                return ("resume", previous_runs[0].stage_run_id)
            else:
                return ("execute", None)

        else:  # overwrite
            return ("execute", None)

    async def create_stage_run(
        self,
        run_id: str,
        stage_name: str,
        requested_mode: Literal["skip", "resume", "overwrite"],
        execution_digest: str,
        attempt_no: int = 1,
    ) -> StageRun:
        """Create a new stage run record."""
        stage_run = StageRun(
            stage_run_id=f"stg_{run_id}_{stage_name}_{attempt_no}",
            run_id=run_id,
            stage_name=stage_name,
            attempt_no=attempt_no,
            status=StageStatus.PENDING,
            requested_mode=requested_mode,
            execution_digest=execution_digest,
            resumable=False,
        )
        await self.db.save_stage_run(stage_run)
        return stage_run

    async def mark_running(self, stage_run_id: str) -> bool:
        """Mark stage as running."""
        stage_run = await self.db.get_stage_run(stage_run_id)
        if not stage_run:
            return False

        stage_run.status = StageStatus.RUNNING
        stage_run.started_at = datetime.utcnow()
        return await self.db.save_stage_run(stage_run)

    async def mark_succeeded(
        self,
        stage_run_id: str,
        output_contract_path: Optional[str] = None,
        output_digest: Optional[str] = None,
        actual_cost_usd: Decimal = Decimal("0"),
    ) -> bool:
        """Mark stage as succeeded."""
        stage_run = await self.db.get_stage_run(stage_run_id)
        if not stage_run:
            return False

        stage_run.status = StageStatus.SUCCEEDED
        stage_run.completed_at = datetime.utcnow()
        stage_run.output_contract_path = output_contract_path
        stage_run.output_digest = output_digest
        stage_run.actual_cost_usd = actual_cost_usd
        return await self.db.save_stage_run(stage_run)

    async def mark_failed(
        self,
        stage_run_id: str,
        error_code: str,
        error_message: str,
        actual_cost_usd: Decimal = Decimal("0"),
    ) -> bool:
        """Mark stage as failed."""
        stage_run = await self.db.get_stage_run(stage_run_id)
        if not stage_run:
            return False

        stage_run.status = StageStatus.FAILED
        stage_run.completed_at = datetime.utcnow()
        stage_run.error_code = error_code
        stage_run.error_message = error_message
        stage_run.actual_cost_usd = actual_cost_usd
        return await self.db.save_stage_run(stage_run)

    async def mark_partial(
        self,
        stage_run_id: str,
        checkpoint_path: str,
        completed_units: int,
        total_units: int,
        actual_cost_usd: Decimal = Decimal("0"),
    ) -> bool:
        """Mark stage as partial (resumable)."""
        stage_run = await self.db.get_stage_run(stage_run_id)
        if not stage_run:
            return False

        stage_run.status = StageStatus.PARTIAL
        stage_run.resumable = True
        stage_run.checkpoint_path = checkpoint_path
        stage_run.completed_units = completed_units
        stage_run.total_units = total_units
        stage_run.completed_at = datetime.utcnow()
        stage_run.actual_cost_usd = actual_cost_usd
        return await self.db.save_stage_run(stage_run)

    async def mark_skipped(
        self,
        stage_run_id: str,
        reused_from_stage_run_id: str,
    ) -> bool:
        """Mark stage as skipped (reused)."""
        stage_run = await self.db.get_stage_run(stage_run_id)
        if not stage_run:
            return False

        stage_run.status = StageStatus.SKIPPED
        stage_run.reused_from_stage_run_id = reused_from_stage_run_id
        stage_run.completed_at = datetime.utcnow()
        return await self.db.save_stage_run(stage_run)

    async def _find_previous_runs(
        self,
        run_id: str,
        stage_name: str,
        execution_digest: str,
        limit: int = 10,
    ) -> list[StageRun]:
        """Find previous runs with same digest."""
        try:
            cursor = await self.db.connection.execute(
                """
                SELECT * FROM stage_runs
                WHERE run_id = ? AND stage_name = ? AND execution_digest = ?
                ORDER BY attempt_no DESC
                LIMIT ?
                """,
                (run_id, stage_name, execution_digest, limit),
            )
            rows = await cursor.fetchall()
            return [StageRun(**dict(row)) for row in rows]
        except Exception:
            return []
