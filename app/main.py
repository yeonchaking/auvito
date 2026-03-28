"""Application initialization and dependency injection."""

from pathlib import Path

from app.settings import load_settings, get_config
from app.storage.sqlite import Database
from app.core.orchestrator import PipelineOrchestrator
from app.core.cost_guardrail import CostGuardrail


class AppContainer:
    """Dependency injection container."""

    def __init__(self):
        """Initialize container."""
        self.settings, self.config = load_settings()

        # Initialize database
        db_path = self.settings.db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = Database(db_path)

        # Initialize guardrails and orchestrator
        self.cost_guardrail = CostGuardrail(
            self.config.get("cost_guardrail", {})
        )
        self.orchestrator = None

    async def init(self):
        """Initialize async components."""
        await self.db.init()
        self.orchestrator = PipelineOrchestrator(
            self.db,
            self.cost_guardrail,
            self.config,
            settings=self.settings,
        )
        await self.orchestrator.initialize()

    async def shutdown(self):
        """Shutdown async components."""
        if self.orchestrator:
            await self.orchestrator.shutdown()


def create_app() -> AppContainer:
    """Create application container."""
    return AppContainer()
