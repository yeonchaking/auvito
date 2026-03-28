"""Typer CLI application."""

import asyncio
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from app.main import create_app
from app.domain.enums import ProjectStatus, StageStatus, ApprovalStatus

app = typer.Typer(help="YouTube content production pipeline")
console = Console()


# ============================================================================
# PROJECT COMMANDS
# ============================================================================


@app.command()
def project_create(
    topic: str = typer.Option(..., help="Project topic/title seed"),
    channel: str = typer.Option("My Channel", help="Channel name"),
    niche: str = typer.Option("General", help="Content niche"),
    duration: int = typer.Option(480, help="Target duration in seconds"),
):
    """Create a new project."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            project = await container.orchestrator.projects.create(
                title_seed=topic,
                channel_name=channel,
                niche=niche,
                target_duration_sec=duration,
            )
            console.print(
                f"[green]✓[/green] Project created: {project.slug} ({project.id})"
            )

            # Run intake stage to create workspace
            result = await container.orchestrator.run_stage(
                slug=project.slug,
                stage_name="intake",
            )
            if result.get("success"):
                console.print("[green]✓[/green] Workspace initialized")
            else:
                console.print(f"[yellow]⚠[/yellow] Workspace init: {result.get('error', 'unknown')}")
        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def project_list():
    """List all projects."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            projects = await container.orchestrator.projects.list_all()

            if not projects:
                console.print("[yellow]No projects found[/yellow]")
                return

            table = Table(title="Projects")
            table.add_column("Slug", style="cyan")
            table.add_column("Title", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Created", style="blue")

            for project in projects:
                table.add_row(
                    project.slug,
                    project.title_seed,
                    project.status.value,
                    project.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)
        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def project_show(slug: str = typer.Argument(..., help="Project slug")):
    """Show project details."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            project = await container.orchestrator.projects.get(slug)
            if not project:
                console.print("[red]✗[/red] Project not found")
                raise typer.Exit(1)

            console.print(f"[cyan]Slug:[/cyan] {project.slug}")
            console.print(f"[cyan]Title:[/cyan] {project.title_seed}")
            console.print(f"[cyan]Channel:[/cyan] {project.channel_name}")
            console.print(f"[cyan]Niche:[/cyan] {project.niche}")
            console.print(f"[cyan]Status:[/cyan] {project.status.value}")
            console.print(f"[cyan]Target Duration:[/cyan] {project.target_duration_sec}s")
            console.print(f"[cyan]Created:[/cyan] {project.created_at.isoformat()}")
        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def project_delete(
    slug: str = typer.Argument(..., help="Project slug"),
    confirm: bool = typer.Option(
        False, "--confirm", help="Skip confirmation prompt"
    ),
):
    """Delete a project."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            project = await container.orchestrator.projects.get(slug)
            if not project:
                console.print("[red]✗[/red] Project not found")
                raise typer.Exit(1)

            if not confirm:
                response = typer.confirm(f"Delete project '{slug}'?")
                if not response:
                    console.print("[yellow]⊘[/yellow] Cancelled")
                    raise typer.Exit(0)

            success = await container.orchestrator.projects.delete(slug)
            if success:
                console.print(f"[green]✓[/green] Project deleted: {slug}")
            else:
                console.print("[red]✗[/red] Failed to delete project")
                raise typer.Exit(1)
        finally:
            await container.shutdown()

    asyncio.run(_run())


# ============================================================================
# STAGE COMMANDS
# ============================================================================


@app.command()
def stage_run(
    slug: str = typer.Argument(..., help="Project slug"),
    stage: str = typer.Argument(..., help="Stage name (intake, benchmark, script, voice, storyboard, assets, render)"),
    mode: str = typer.Option(
        "resume", help="Execution mode: skip, resume, or overwrite"
    ),
):
    """Run a single stage."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            console.print(f"[cyan]Running stage:[/cyan] {stage} ({mode})")

            result = await container.orchestrator.run_stage(
                slug=slug,
                stage_name=stage,
                mode=mode,
            )

            if result.get("success"):
                console.print(f"[green]✓[/green] Stage '{stage}' completed: {result.get('result', '')}")
            else:
                console.print(f"[red]✗[/red] Stage '{stage}' failed: {result.get('error', 'unknown')}")
                raise typer.Exit(1)
        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def stage_status(slug: str = typer.Argument(..., help="Project slug")):
    """Show stage execution status."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            project = await container.orchestrator.projects.get(slug)
            if not project:
                console.print("[red]✗[/red] Project not found")
                raise typer.Exit(1)

            console.print(f"[cyan]Project:[/cyan] {slug}")
            console.print(f"[cyan]Current Stage:[/cyan] {project.current_stage or 'None'}")
            console.print(f"[cyan]Status:[/cyan] {project.status.value}")
        finally:
            await container.shutdown()

    asyncio.run(_run())


# ============================================================================
# PIPELINE COMMANDS
# ============================================================================


@app.command()
def pipeline_run(
    slug: str = typer.Argument(..., help="Project slug"),
    from_stage: Optional[str] = typer.Option(
        None, "--from", help="Start from stage"
    ),
    until_stage: Optional[str] = typer.Option(None, "--until", help="End at stage"),
    mode: str = typer.Option("resume", help="Execution mode"),
    run_id: Optional[str] = typer.Option(None, help="Specific run ID to resume"),
    run_all: bool = typer.Option(False, "--all", help="Run all stages"),
    approve_all: bool = typer.Option(
        False, "--approve-all", help="Auto-approve non-upload checkpoints"
    ),
):
    """Run pipeline for a project."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            console.print(f"[cyan]Pipeline Run:[/cyan] {slug}")
            console.print(f"[cyan]Mode:[/cyan] {mode}")

            if run_all:
                from_stage = None
                until_stage_val = None
            else:
                until_stage_val = until_stage

            result = await container.orchestrator.run_pipeline(
                slug=slug,
                from_stage=from_stage,
                until_stage=until_stage_val,
                mode=mode,
                run_id=run_id,
                approve_all=approve_all,
            )

            console.print(f"[cyan]Run ID:[/cyan] {result.get('run_id', 'N/A')}")

            for stage_name, stage_result in result.get("stages", {}).items():
                if stage_result.get("success"):
                    console.print(f"  [green]✓[/green] {stage_name}: {stage_result.get('result', 'done')}")
                elif stage_result.get("status") == "awaiting_approval":
                    console.print(f"  [yellow]⏸[/yellow] {stage_name}: {stage_result.get('message', 'awaiting approval')}")
                else:
                    console.print(f"  [red]✗[/red] {stage_name}: {stage_result.get('error', 'failed')}")

            if result.get("completed"):
                console.print("\n[green]✓ Pipeline completed successfully[/green]")
            else:
                console.print("\n[yellow]Pipeline stopped (check results above)[/yellow]")
        finally:
            await container.shutdown()

    asyncio.run(_run())


# ============================================================================
# APPROVAL COMMANDS
# ============================================================================


@app.command()
def approvals_list(slug: Optional[str] = typer.Argument(None)):
    """List pending approvals."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            if slug:
                approvals = await container.orchestrator.approvals.list_pending(slug)
            else:
                approvals = await container.orchestrator.approvals.list_all_pending()

            if not approvals:
                console.print("[yellow]No pending approvals[/yellow]")
                return

            table = Table(title="Pending Approvals")
            table.add_column("ID", style="cyan")
            table.add_column("Checkpoint", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Created", style="blue")

            for approval in approvals:
                table.add_row(
                    approval.approval_id,
                    approval.checkpoint_name,
                    approval.status,
                    approval.created_at.strftime("%Y-%m-%d %H:%M") if approval.created_at else "N/A",
                )

            console.print(table)
        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def approve(
    approval_id: str = typer.Argument(..., help="Approval ID"),
    comment: Optional[str] = typer.Option(None, help="Approval comment"),
):
    """Approve a checkpoint."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            success = await container.orchestrator.approvals.approve(
                approval_id, reviewer="cli_user", comment=comment
            )
            if success:
                console.print(f"[green]✓[/green] Approved: {approval_id}")
            else:
                console.print("[red]✗[/red] Approval not found")
                raise typer.Exit(1)
        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def reject(
    approval_id: str = typer.Argument(..., help="Approval ID"),
    reason: str = typer.Option(..., help="Rejection reason"),
):
    """Reject a checkpoint."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            success = await container.orchestrator.approvals.reject(
                approval_id, reviewer="cli_user", reason=reason
            )
            if success:
                console.print(f"[green]✓[/green] Rejected: {approval_id}")
            else:
                console.print("[red]✗[/red] Approval not found")
                raise typer.Exit(1)
        finally:
            await container.shutdown()

    asyncio.run(_run())


# ============================================================================
# AUTH COMMANDS
# ============================================================================


@app.command()
def auth_login():
    """Login with OAuth2 (Google). [Phase 2]"""
    console.print("[yellow]⊘[/yellow] OAuth2 login is Phase 2. Not yet implemented.")


@app.command()
def auth_status():
    """Check authentication status."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            settings = container.settings
            console.print("[cyan]Authentication Status:[/cyan]")
            console.print(f"  YouTube API Key: {'[green]✓ Set[/green]' if settings.youtube_api_key else '[red]✗ Missing[/red]'}")
            console.print(f"  Anthropic API Key: {'[green]✓ Set[/green]' if settings.anthropic_api_key else '[red]✗ Missing[/red]'}")
            console.print(f"  OpenAI API Key: {'[green]✓ Set[/green]' if settings.openai_api_key else '[red]✗ Missing[/red]'}")
            console.print(f"  Google OAuth: [yellow]Phase 2[/yellow]")
        finally:
            await container.shutdown()

    asyncio.run(_run())


# ============================================================================
# COST COMMANDS
# ============================================================================


@app.command()
def cost_report(slug: str = typer.Argument(..., help="Project slug")):
    """Show cost report for project."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            project = await container.orchestrator.projects.get(slug)
            if not project:
                console.print("[red]✗[/red] Project not found")
                raise typer.Exit(1)

            console.print(f"[cyan]Cost Report:[/cyan] {slug}")
            console.print("[yellow]⊘[/yellow] Detailed cost reporting coming in Phase 2")
        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def cost_estimate(
    slug: str = typer.Argument(..., help="Project slug"),
    stage: str = typer.Argument(..., help="Stage name"),
):
    """Estimate cost for a stage."""
    console.print(f"[cyan]Cost Estimate:[/cyan] {slug} / {stage}")

    estimates = {
        "benchmark": "$0.10 ~ $0.50 (YouTube API + LLM analysis)",
        "script": "$0.20 ~ $0.80 (3x LLM calls: strategist/writer/reviewer)",
        "voice": "$0.00 ~ $0.01 (Edge TTS free + STT ~$0.006/min)",
        "storyboard": "$0.10 ~ $0.40 (LLM storyboard generation)",
        "assets": "$0.40 ~ $8.00 (gpt-image-1 ~$0.04/image, max 30 images)",
        "render": "$0.00 (local FFmpeg processing)",
    }

    if stage in estimates:
        console.print(f"  Estimated: {estimates[stage]}")
    else:
        console.print(f"[yellow]Unknown stage: {stage}[/yellow]")


# ============================================================================
# ARTIFACT COMMANDS
# ============================================================================


@app.command()
def artifact_list(
    slug: str = typer.Argument(..., help="Project slug"),
    stage: Optional[str] = typer.Option(None, help="Filter by stage"),
):
    """List artifacts for project."""
    from pathlib import Path

    workspace = Path("workspace") / "projects" / slug
    if not workspace.exists():
        console.print("[red]✗[/red] Project workspace not found")
        raise typer.Exit(1)

    table = Table(title=f"Artifacts: {slug}")
    table.add_column("Stage", style="cyan")
    table.add_column("File", style="magenta")
    table.add_column("Size", style="green")

    stage_dirs = sorted(workspace.iterdir()) if workspace.exists() else []
    for d in stage_dirs:
        if not d.is_dir():
            continue
        if stage and stage not in d.name:
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                size = f.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                table.add_row(d.name, str(f.relative_to(d)), size_str)

    console.print(table)


# ============================================================================
# CONFIG COMMANDS
# ============================================================================


@app.command()
def config_show():
    """Show current configuration."""
    from app.settings import load_settings
    import yaml

    settings, config = load_settings()

    console.print("[cyan]API Keys:[/cyan]")
    console.print(f"  YouTube: {'✓ Set' if settings.youtube_api_key else '✗ Missing'}")
    console.print(f"  Anthropic: {'✓ Set' if settings.anthropic_api_key else '✗ Missing'}")
    console.print(f"  OpenAI: {'✓ Set' if settings.openai_api_key else '✗ Missing'}")
    console.print()
    console.print("[cyan]Configuration:[/cyan]")
    console.print(yaml.dump(config, default_flow_style=False, allow_unicode=True))


@app.command()
def config_check():
    """Check configuration validity."""
    from app.settings import load_settings

    try:
        settings, config = load_settings()
        console.print("[green]✓[/green] Configuration file loaded successfully")

        issues = []
        if not settings.youtube_api_key:
            issues.append("YOUTUBE_API_KEY not set in .env")
        if not settings.anthropic_api_key:
            issues.append("ANTHROPIC_API_KEY not set in .env")
        if not settings.openai_api_key:
            issues.append("OPENAI_API_KEY not set in .env")

        if issues:
            console.print("[yellow]Warnings:[/yellow]")
            for issue in issues:
                console.print(f"  [yellow]⚠[/yellow] {issue}")
        else:
            console.print("[green]✓[/green] All API keys configured")

    except Exception as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
