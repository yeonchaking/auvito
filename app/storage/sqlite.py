"""SQLite storage layer."""

import aiosqlite
from pathlib import Path
from typing import Optional

from app.domain.models import Project, StageRun, Artifact, Approval


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str):
        """Initialize database."""
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None

    async def init(self):
        """Initialize database and create tables."""
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row

        # Enable WAL mode
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA busy_timeout=5000")

        # Create tables
        await self.connection.executescript(
            """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            title_seed TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            niche TEXT NOT NULL,
            language TEXT DEFAULT 'ko-KR',
            target_duration_sec INTEGER DEFAULT 480,
            status TEXT NOT NULL,
            current_stage TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS stage_runs (
            stage_run_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            attempt_no INTEGER NOT NULL,
            status TEXT NOT NULL,
            requested_mode TEXT NOT NULL,
            execution_digest TEXT NOT NULL,
            resumable BOOLEAN DEFAULT 0,
            checkpoint_path TEXT,
            completed_units INTEGER DEFAULT 0,
            total_units INTEGER,
            output_contract_path TEXT,
            output_digest TEXT,
            reused_from_stage_run_id TEXT,
            resumed_from_stage_run_id TEXT,
            actual_cost_usd DECIMAL DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            error_code TEXT,
            error_message TEXT,
            UNIQUE(run_id, stage_name, attempt_no),
            FOREIGN KEY(run_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            artifact_type TEXT NOT NULL,
            run_id TEXT NOT NULL,
            stage_run_id TEXT NOT NULL,
            uri TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            parents TEXT,
            source_kind TEXT NOT NULL,
            generator TEXT,
            source_refs TEXT,
            license_info TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES projects(id),
            FOREIGN KEY(stage_run_id) REFERENCES stage_runs(stage_run_id)
        );

        CREATE TABLE IF NOT EXISTS approvals (
            approval_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            checkpoint_name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_ref TEXT NOT NULL,
            status TEXT NOT NULL,
            estimated_incremental_cost_usd DECIMAL,
            summary TEXT,
            diff_ref TEXT,
            reviewer TEXT,
            decision_comment TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY(run_id) REFERENCES projects(id)
        );

        CREATE INDEX IF NOT EXISTS idx_stage_runs_run_id ON stage_runs(run_id);
        CREATE INDEX IF NOT EXISTS idx_stage_runs_status ON stage_runs(status);
        CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);
        CREATE INDEX IF NOT EXISTS idx_approvals_run_id ON approvals(run_id);
        CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
        """
        )
        await self.connection.commit()

    async def close(self):
        """Close database connection."""
        if self.connection:
            await self.connection.close()

    async def save_project(self, project: Project) -> bool:
        """Save project."""
        try:
            await self.connection.execute(
                """
                INSERT OR REPLACE INTO projects
                (id, slug, title_seed, channel_name, niche, language, target_duration_sec, status, current_stage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(project.id),
                    project.slug,
                    project.title_seed,
                    project.channel_name,
                    project.niche,
                    project.language,
                    project.target_duration_sec,
                    project.status.value,
                    project.current_stage,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
            await self.connection.commit()
            return True
        except Exception:
            return False

    async def get_project(self, slug: str) -> Optional[Project]:
        """Get project by slug."""
        try:
            cursor = await self.connection.execute(
                "SELECT * FROM projects WHERE slug = ?", (slug,)
            )
            row = await cursor.fetchone()
            if row:
                return Project(**dict(row))
        except Exception:
            pass
        return None

    async def save_stage_run(self, stage_run: StageRun) -> bool:
        """Save stage run."""
        try:
            await self.connection.execute(
                """
                INSERT OR REPLACE INTO stage_runs
                (stage_run_id, run_id, stage_name, attempt_no, status, requested_mode, execution_digest,
                 resumable, checkpoint_path, completed_units, total_units, output_contract_path,
                 output_digest, reused_from_stage_run_id, resumed_from_stage_run_id,
                 actual_cost_usd, started_at, completed_at, error_code, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stage_run.stage_run_id,
                    stage_run.run_id,
                    stage_run.stage_name,
                    stage_run.attempt_no,
                    stage_run.status.value,
                    stage_run.requested_mode,
                    stage_run.execution_digest,
                    stage_run.resumable,
                    stage_run.checkpoint_path,
                    stage_run.completed_units,
                    stage_run.total_units,
                    stage_run.output_contract_path,
                    stage_run.output_digest,
                    stage_run.reused_from_stage_run_id,
                    stage_run.resumed_from_stage_run_id,
                    str(stage_run.actual_cost_usd),
                    stage_run.started_at.isoformat() if stage_run.started_at else None,
                    stage_run.completed_at.isoformat() if stage_run.completed_at else None,
                    stage_run.error_code,
                    stage_run.error_message,
                ),
            )
            await self.connection.commit()
            return True
        except Exception:
            return False

    async def get_stage_run(self, stage_run_id: str) -> Optional[StageRun]:
        """Get stage run by ID."""
        try:
            cursor = await self.connection.execute(
                "SELECT * FROM stage_runs WHERE stage_run_id = ?", (stage_run_id,)
            )
            row = await cursor.fetchone()
            if row:
                return StageRun(**dict(row))
        except Exception:
            pass
        return None

    async def save_artifact(self, artifact: Artifact) -> bool:
        """Save artifact."""
        try:
            await self.connection.execute(
                """
                INSERT OR REPLACE INTO artifacts
                (artifact_id, artifact_type, run_id, stage_run_id, uri, sha256, parents,
                 source_kind, generator, source_refs, license_info, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.artifact_type,
                    artifact.run_id,
                    artifact.stage_run_id,
                    artifact.uri,
                    artifact.sha256,
                    ",".join(artifact.parents),
                    artifact.source_kind,
                    artifact.generator,
                    artifact.source_refs,
                    artifact.license_info,
                    artifact.created_at.isoformat(),
                ),
            )
            await self.connection.commit()
            return True
        except Exception:
            return False

    async def save_approval(self, approval: Approval) -> bool:
        """Save approval."""
        try:
            await self.connection.execute(
                """
                INSERT OR REPLACE INTO approvals
                (approval_id, run_id, checkpoint_name, entity_type, entity_ref, status,
                 estimated_incremental_cost_usd, summary, diff_ref, reviewer, decision_comment,
                 created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.run_id,
                    approval.checkpoint_name,
                    approval.entity_type,
                    approval.entity_ref,
                    approval.status.value,
                    str(approval.estimated_incremental_cost_usd),
                    approval.summary,
                    approval.diff_ref,
                    approval.reviewer,
                    approval.decision_comment,
                    approval.created_at.isoformat(),
                    approval.resolved_at.isoformat() if approval.resolved_at else None,
                ),
            )
            await self.connection.commit()
            return True
        except Exception:
            return False

    async def get_approval(self, approval_id: str) -> Optional[Approval]:
        """Get approval by ID."""
        try:
            cursor = await self.connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            )
            row = await cursor.fetchone()
            if row:
                return Approval(**dict(row))
        except Exception:
            pass
        return None
