"""Project management CRUD operations."""

from uuid import uuid4
from datetime import datetime
from typing import Optional

from app.domain.models import Project
from app.domain.enums import ProjectStatus
from app.storage.sqlite import Database
from app.utils.slug import create_slug


class ProjectManager:
    """Manages project lifecycle."""

    def __init__(self, db: Database):
        """Initialize project manager."""
        self.db = db

    async def create(
        self,
        title_seed: str,
        channel_name: str,
        niche: str,
        language: str = "ko-KR",
        target_duration_sec: int = 480,
    ) -> Project:
        """Create a new project."""
        project = Project(
            id=uuid4(),
            slug=create_slug(title_seed),
            title_seed=title_seed,
            channel_name=channel_name,
            niche=niche,
            language=language,
            target_duration_sec=target_duration_sec,
            status=ProjectStatus.CREATED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await self.db.save_project(project)
        return project

    async def get(self, slug: str) -> Optional[Project]:
        """Get project by slug."""
        return await self.db.get_project(slug)

    async def update_status(
        self, slug: str, new_status: ProjectStatus, current_stage: Optional[str] = None
    ) -> bool:
        """Update project status."""
        project = await self.get(slug)
        if not project:
            return False

        project.status = new_status
        project.current_stage = current_stage
        project.updated_at = datetime.utcnow()

        return await self.db.save_project(project)

    async def list_all(self) -> list[Project]:
        """List all projects."""
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            return [Project(**dict(row)) for row in rows]
        except Exception:
            return []

    async def delete(self, slug: str) -> bool:
        """Delete a project."""
        try:
            await self.db.connection.execute("DELETE FROM projects WHERE slug = ?", (slug,))
            await self.db.connection.commit()
            return True
        except Exception:
            return False
