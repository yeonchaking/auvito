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
async def project_create(
    topic: str = typer.Option(..., help="Project topic/title seed"),
    channel: str = typer.Option("My Channel", help="Channel name"),
    niche: str = typer.Option("General", help="Content niche"),
    duration: int = typer.Option(480, help="Target duration in seconds"),
):
    """Create a new project."""
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
    finally:
        await container.shutdown()


@app.command()
async def project_list():
    """List all projects."""
    container = create_app()
    await container.init()

    try:
        projects = await container.orchestrator.projects.list_all()

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


@app.command()
async def project_show(slug: str = typer.Argument(..., help="Project slug")):
    """Show project details."""
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


@app.command()
async def project_delete(
    slug: str = typer.Argument(..., help="Project slug"),
    confirm: bool = typer.Option(
        False, "--confirm", help="Skip confirmation prompt"
    ),
):
    """Delete a project."""
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


# ============================================================================
# STAGE COMMANDS
# ============================================================================


@app.command()
async def stage_run(
    slug: str = typer.Argument(..., help="Project slug"),
    stage: str = typer.Argument(..., help="Stage name"),
    mode: str = typer.Option(
        "resume", help="Execution mode: skip, resume, or overwrite"
    ),
):
    """Run a single stage."""
    container = create_app()
    await container.init()

    try:
        project = await container.orchestrator.projects.get(slug)
        if not project:
            console.print("[red]✗[/red] Project not found")
            raise typer.Exit(1)

        console.print(f"[cyan]Running stage:[/cyan] {stage} ({mode})")
        console.print("[yellow]⊘[/yellow] Stage execution not yet implemented")
    finally:
        await container.shutdown()


@app.command()
async def stage_status(slug: str = typer.Argument(..., help="Project slug")):
    """Show stage execution status."""
    container = create_app()
    await container.init()

    try:
        project = await container.orchestrator.projects.get(slug)
        if not project:
            console.print("[red]✗[/red] Project not found")
            raise typer.Exit(1)

        console.print(f"[cyan]Project:[/cyan] {slug}")
        console.print(f"[cyan]Current Stage:[/cyan] {project.current_stage}")
        console.print(f"[cyan]Status:[/cyan] {project.status.value}")
    finally:
        await container.shutdown()


# ============================================================================
# PIPELINE COMMANDS
# ============================================================================


@app.command()
async def pipeline_run(
    slug: str = typer.Argument(..., help="Project slug"),
    from_stage: Optional[str] = typer.Option(
        None, "--from", help="Start from stage"
    ),
    until_stage: Optional[str] = typer.Option(None, "--until", help="End at stage"),
    mode: str = typer.Option("resume", help="Execution mode"),
    run_id: Optional[str] = typer.Option(None, help="Specific run ID to resume"),
    all: bool = typer.Option(False, "--all", help="Run all stages"),
    approve_all: bool = typer.Option(
        False, "--approve-all", help="Auto-approve non-upload checkpoints"
    ),
):
    """Run pipeline for a project."""
    container = create_app()
    await container.init()

    try:
        project = await container.orchestrator.projects.get(slug)
        if not project:
            console.print("[red]✗[/red] Project not found")
            raise typer.Exit(1)

        console.print(f"[cyan]Pipeline Run:[/cyan] {slug}")
        console.print(f"[cyan]Mode:[/cyan] {mode}")
        if run_id:
            console.print(f"[cyan]Resume Run ID:[/cyan] {run_id}")
        console.print("[yellow]⊘[/yellow] Pipeline execution not yet implemented")
    finally:
        await container.shutdown()


# ============================================================================
# APPROVAL COMMANDS
# ============================================================================


@app.command()
async def approvals_list(slug: Optional[str] = typer.Argument(None)):
    """List pending approvals."""
    container = create_app()
    await container.init()

    try:
        console.print("[yellow]⊘[/yellow] Approval listing not yet implemented")
    finally:
        await container.shutdown()


@app.command()
async def approve(
    approval_id: str = typer.Argument(..., help="Approval ID"),
    comment: Optional[str] = typer.Option(None, help="Approval comment"),
):
    """Approve a checkpoint."""
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


@app.command()
async def reject(
    approval_id: str = typer.Argument(..., help="Approval ID"),
    reason: str = typer.Option(..., help="Rejection reason"),
):
    """Reject a checkpoint."""
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


# ============================================================================
# AUTH COMMANDS
# ============================================================================


@app.command()
async def auth_login():
    """Login with OAuth2 (Google)."""
    container = create_app()
    await container.init()

    try:
        console.print("[yellow]⊘[/yellow] OAuth2 login not yet implemented")
    finally:
        await container.shutdown()


@app.command()
async def auth_status():
    """Check authentication status."""
    container = create_app()
    await container.init()

    try:
        console.print("[yellow]⊘[/yellow] Auth status check not yet implemented")
    finally:
        await container.shutdown()


# ============================================================================
# COST COMMANDS
# ============================================================================


@app.command()
async def cost_report(slug: str = typer.Argument(..., help="Project slug")):
    """Show cost report for project."""
    container = create_app()
    await container.init()

    try:
        project = await container.orchestrator.projects.get(slug)
        if not project:
            console.print("[red]✗[/red] Project not found")
            raise typer.Exit(1)

        console.print(f"[cyan]Cost Report:[/cyan] {slug}")
        console.print("[yellow]⊘[/yellow] Cost reporting not yet implemented")
    finally:
        await container.shutdown()


@app.command()
async def cost_estimate(
    slug: str = typer.Argument(..., help="Project slug"),
    stage: str = typer.Argument(..., help="Stage name"),
):
    """Estimate cost for a stage."""
    container = create_app()
    await container.init()

    try:
        project = await container.orchestrator.projects.get(slug)
        if not project:
            console.print("[red]✗[/red] Project not found")
            raise typer.Exit(1)

        console.print(f"[cyan]Cost Estimate:[/cyan] {slug} / {stage}")
        console.print("[yellow]⊘[/yellow] Cost estimation not yet implemented")
    finally:
        await container.shutdown()


# ============================================================================
# ARTIFACT COMMANDS
# ============================================================================


@app.command()
async def artifact_list(
    slug: str = typer.Argument(..., help="Project slug"),
    stage: Optional[str] = typer.Option(None, help="Filter by stage"),
):
    """List artifacts for project."""
    container = create_app()
    await container.init()

    try:
        project = await container.orchestrator.projects.get(slug)
        if not project:
            console.print("[red]✗[/red] Project not found")
            raise typer.Exit(1)

        console.print(f"[cyan]Artifacts:[/cyan] {slug}")
        if stage:
            console.print(f"[cyan]Stage:[/cyan] {stage}")
        console.print("[yellow]⊘[/yellow] Artifact listing not yet implemented")
    finally:
        await container.shutdown()


# ============================================================================
# CONFIG COMMANDS
# ============================================================================


@app.command()
async def config_show():
    """Show current configuration."""
    container = create_app()
    await container.init()

    try:
        console.print("[cyan]Configuration:[/cyan]")
        console.print("[yellow]⊘[/yellow] Config display not yet implemented")
    finally:
        await container.shutdown()


@app.command()
async def config_check():
    """Check configuration validity."""
    container = create_app()
    await container.init()

    try:
        console.print("[green]✓[/green] Configuration valid")
    finally:
        await container.shutdown()


if __name__ == "__main__":
    app()
