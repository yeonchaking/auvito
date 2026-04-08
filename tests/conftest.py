"""Pytest configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path

from app.main import AppContainer
from app.storage.sqlite import Database
from app.core.orchestrator import PipelineOrchestrator
from app.core.cost_guardrail import CostGuardrail
from app.providers.fake import (
    FakeResearchProvider,
    FakeNarrativeProvider,
    FakeTTSProvider,
    FakeSTTProvider,
    FakeAssetProvider,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        yield db


@pytest.fixture
async def app_container():
    """Create app container for testing."""
    container = AppContainer()
    # Use temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        container.settings.db_path = str(Path(tmpdir) / "test.db")
        await container.init()
        yield container
        await container.shutdown()


@pytest.fixture
def fake_research_provider():
    """Provide fake research provider."""
    return FakeResearchProvider()


@pytest.fixture
def fake_narrative_provider():
    """Provide fake narrative provider."""
    return FakeNarrativeProvider()


@pytest.fixture
def fake_tts_provider():
    """Provide fake TTS provider."""
    return FakeTTSProvider()


@pytest.fixture
def fake_stt_provider():
    """Provide fake STT provider."""
    return FakeSTTProvider()


@pytest.fixture
def fake_asset_provider():
    """Provide fake asset provider."""
    return FakeAssetProvider()


