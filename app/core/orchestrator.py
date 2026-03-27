"""Pipeline orchestrator for coordinating stages."""

from typing import Optional
from app.storage.sqlite import Database
from app.core.project_manager import ProjectManager
from app.core.stage_executor import StageExecutor
from app.core.approval_service import ApprovalService
from app.core.artifact_registry import ArtifactRegistry
from app.core.cost_guardrail import CostGuardrail
from app.core.quality_gate import QualityGateRunner


class PipelineOrchestrator:
    """Orchestrates pipeline execution."""

    def __init__(
        self,
        db: Database,
        cost_guardrail: CostGuardrail,
        config: dict,
    ):
        """Initialize orchestrator."""
        self.db = db
        self.config = config
        self.cost_guardrail = cost_guardrail

        # Initialize sub-managers
        self.projects = ProjectManager(db)
        self.executor = StageExecutor(db)
        self.approvals = ApprovalService(db)
        self.artifacts = ArtifactRegistry(db)
        self.quality_gate = QualityGateRunner()

    async def initialize(self):
        """Initialize database."""
        await self.db.init()

    async def shutdown(self):
        """Close database connection."""
        await self.db.close()
