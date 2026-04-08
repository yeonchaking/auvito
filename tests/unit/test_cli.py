"""CLI regression tests."""

from typer.testing import CliRunner

import app.cli as cli


class _DummyOrchestrator:
    def __init__(self):
        self.calls = []

    async def run_pipeline(
        self,
        slug,
        from_stage=None,
        until_stage=None,
        mode="resume",
        run_id=None,
        approve_all=False,
    ):
        self.calls.append(
            {
                "slug": slug,
                "from_stage": from_stage,
                "until_stage": until_stage,
                "mode": mode,
                "run_id": run_id,
                "approve_all": approve_all,
            }
        )
        return {"run_id": "run-123", "stages": {}, "completed": True}


class _DummyContainer:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.initialized = False
        self.shutdown_called = False

    async def init(self):
        self.initialized = True

    async def shutdown(self):
        self.shutdown_called = True


def test_pipeline_run_uses_default_stage_range_without_scoping_error(monkeypatch):
    orchestrator = _DummyOrchestrator()
    container = _DummyContainer(orchestrator)
    runner = CliRunner()

    monkeypatch.setattr(cli, "create_app", lambda: container)

    result = runner.invoke(cli.app, ["pipeline-run", "demo-project"])

    assert result.exit_code == 0, result.output
    assert container.initialized is True
    assert container.shutdown_called is True
    assert orchestrator.calls == [
        {
            "slug": "demo-project",
            "from_stage": None,
            "until_stage": None,
            "mode": "resume",
            "run_id": None,
            "approve_all": False,
        }
    ]
