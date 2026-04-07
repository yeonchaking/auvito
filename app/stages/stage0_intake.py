"""Stage 0: Project intake and setup."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.enums import ProjectStatus
from app.domain.models import Project
from app.domain.schemas import BenchmarkRequest
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.storage.sqlite import Database


class IntakeStage(BaseStage):
    """Stage 0: Project creation and setup.

    Creates project workspace folder structure and initialization files.
    """

    stage_name = "intake"

    def __init__(self, db: Database, workspace_root: str):
        """Initialize intake stage.

        Args:
            db: Database connection
            workspace_root: Root directory for workspaces
        """
        self.db = db
        self.workspace_root = workspace_root

    async def execute(self, project: Project) -> Project:
        """Create project directory structure and initialize metadata.

        Args:
            project: Project instance to initialize

        Returns:
            The initialized project with workspace set up
        """
        # Create workspace directory structure
        project_workspace = Path(self.workspace_root) / "projects" / project.slug
        await self._create_directory_structure(project_workspace)

        # Create project.json (derived snapshot)
        project_snapshot = {
            "id": str(project.id),
            "slug": project.slug,
            "title_seed": project.title_seed,
            "channel_name": project.channel_name,
            "niche": project.niche,
            "language": project.language,
            "target_duration_sec": project.target_duration_sec,
            "status": project.status.value,
            "current_stage": project.current_stage,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }
        await FileStorage.save_json(
            str(project_workspace / "project.json"), project_snapshot
        )

        # Create config_snapshot.json (minimal current settings)
        config_snapshot = {
            "language": project.language,
            "target_duration_sec": project.target_duration_sec,
            "niche": project.niche,
            "snapshot_created_at": datetime.utcnow().isoformat(),
        }
        await FileStorage.save_json(
            str(project_workspace / "config_snapshot.json"), config_snapshot
        )

        # Create cost_summary.json (initial zeroed out)
        cost_summary = {
            "run_id": str(project.id),
            "total_cost_usd": "0.00",
            "by_stage": {
                "intake": "0.00",
                "benchmark": "0.00",
                "script": "0.00",
                "voice": "0.00",
                "storyboard": "0.00",
                "assets": "0.00",
                "render": "0.00",
                "thumbnail": "0.00",
            },
            "created_at": datetime.utcnow().isoformat(),
        }
        await FileStorage.save_json(
            str(project_workspace / "cost_summary.json"), cost_summary
        )

        # Register project in SQLite
        await self.db.save_project(project)

        return project

    async def _create_directory_structure(self, project_workspace: Path) -> None:
        """Create all required subdirectories for the project.

        Args:
            project_workspace: Root project workspace directory
        """
        # Main stage directories
        stage_dirs = [
            "00_intake",
            "01_benchmark",
            "02_script",
            "03_voice",
            "04_storyboard",
            "05_assets",
            "06_render",
            "07_thumbnail",
        ]

        for stage_dir in stage_dirs:
            (project_workspace / stage_dir).mkdir(parents=True, exist_ok=True)

        # Asset subdirectories
        (project_workspace / "05_assets" / "images").mkdir(parents=True, exist_ok=True)
        (project_workspace / "05_assets" / "videos").mkdir(parents=True, exist_ok=True)

        # Metadata and system directories
        (project_workspace / "logs").mkdir(parents=True, exist_ok=True)
        (project_workspace / "logs" / "llm_calls").mkdir(parents=True, exist_ok=True)
        (project_workspace / "approvals").mkdir(parents=True, exist_ok=True)
        (project_workspace / "provenance").mkdir(parents=True, exist_ok=True)

        # Voice subdirectory
        (project_workspace / "03_voice" / "transcripts").mkdir(parents=True, exist_ok=True)

        # Benchmark subdirectory
        (project_workspace / "01_benchmark" / "transcripts").mkdir(
            parents=True, exist_ok=True
        )
