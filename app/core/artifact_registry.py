"""Artifact registry for tracking generated assets."""

from typing import Optional
from app.domain.models import Artifact
from app.storage.sqlite import Database


class ArtifactRegistry:
    """Registry for tracking and retrieving artifacts."""

    def __init__(self, db: Database):
        """Initialize registry."""
        self.db = db

    async def register(self, artifact: Artifact) -> bool:
        """Register an artifact."""
        return await self.db.save_artifact(artifact)

    async def get(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID."""
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            )
            row = await cursor.fetchone()
            if row:
                return Artifact(**dict(row))
        except Exception:
            pass
        return None

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        """List artifacts for a run."""
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            )
            rows = await cursor.fetchall()
            return [Artifact(**dict(row)) for row in rows]
        except Exception:
            return []

    async def list_by_stage(self, stage_run_id: str) -> list[Artifact]:
        """List artifacts for a stage run."""
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM artifacts WHERE stage_run_id = ? ORDER BY created_at DESC",
                (stage_run_id,),
            )
            rows = await cursor.fetchall()
            return [Artifact(**dict(row)) for row in rows]
        except Exception:
            return []
