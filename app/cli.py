"""Typer CLI application."""

import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.text import Text
from rich import box

from app.main import create_app
from app.domain.enums import ProjectStatus, StageStatus, ApprovalStatus

app = typer.Typer(help="YouTube content production pipeline")
console = Console()

# 파이프라인 스테이지 순서 (intake 제외)
PIPELINE_STAGES = [
    "benchmark",
    "script",
    "voice",
    "storyboard",
    "assets",
    "render",
    "thumbnail",
]

STAGE_LABELS = {
    "benchmark": "벤치마크 분석",
    "script"   : "스크립트 생성",
    "voice"    : "내레이션 녹음",
    "storyboard": "스토리보드 구성",
    "assets"   : "이미지 생성",
    "render"   : "영상 렌더링",
    "thumbnail": "썸네일 제작",
}

# ── 에러 안내 ─────────────────────────────────────────────────────────────────

ERROR_HINTS: list[tuple[str, str]] = [
    ("ANTHROPIC_API_KEY",  "Anthropic API 키가 없거나 잘못됐어요. .env 파일의 ANTHROPIC_API_KEY를 확인해주세요."),
    ("OPENAI_API_KEY",     "OpenAI API 키가 없거나 잘못됐어요. .env 파일의 OPENAI_API_KEY를 확인해주세요."),
    ("rate_limit",         "API 요청 한도를 초과했어요. 잠시 후 다시 시도하거나 유료 플랜을 확인해주세요."),
    ("content_policy",     "이미지 생성 중 콘텐츠 정책 위반이 발생했어요. 더 중립적인 주제로 다시 시도해주세요."),
    ("ffmpeg",             "FFmpeg 처리 중 오류가 생겼어요. FFmpeg 설치 여부를 확인해주세요 (ffmpeg -version)."),
    ("WinError 32",        "파일이 다른 프로세스에 잠겨 있어요. 잠시 기다린 후 resume 명령으로 재시도해주세요."),
    ("No such file",       "필요한 파일이 없어요. 이전 스테이지가 완료됐는지 stage-status 명령으로 확인해주세요."),
    ("ConnectionError",    "네트워크 연결 오류예요. 인터넷 연결을 확인하고 resume으로 재시도해주세요."),
    ("TimeoutError",       "API 응답 시간이 초과됐어요. resume 명령으로 재시도해주세요."),
]


def _friendly_error(error_text: str) -> str:
    """에러 메시지를 사용자 친화적으로 변환."""
    lowered = error_text.lower()
    for keyword, hint in ERROR_HINTS:
        if keyword.lower() in lowered:
            return hint
    return f"오류가 발생했어요: {error_text[:120]}"


def _print_error_panel(stage: str, error: str, slug: str) -> None:
    """스테이지 실패 시 에러 패널 출력."""
    hint = _friendly_error(error)
    body = Text()
    body.append("스테이지  : ", style="dim")
    body.append(f"{STAGE_LABELS.get(stage, stage)}\n", style="bold red")
    body.append("원인      : ", style="dim")
    body.append(f"{hint}\n\n", style="yellow")
    body.append("재시도    : ", style="dim")
    body.append(f"python -m app.cli resume {slug}", style="cyan bold")
    console.print(Panel(body, title="[bold red]✗ 스테이지 실패[/bold red]", border_style="red"))


def _print_complete_banner(slug: str, result_path: Optional[str] = None) -> None:
    """완료 배너 출력."""
    body = Text()
    body.append("🎉 영상 제작이 완료됐어요!\n\n", style="bold green")
    if result_path:
        body.append("결과물 위치: ", style="dim")
        body.append(f"{result_path}\n", style="cyan bold")
    body.append("\n")
    body.append("다음 단계  : ", style="dim")
    body.append("RESULT 폴더에서 draft.mp4 파일을 확인하세요.", style="white")
    console.print(Panel(body, title="[bold green]✓ 완료[/bold green]", border_style="green"))


# ============================================================================
# PROJECT COMMANDS
# ============================================================================


@app.command()
def new():
    """새 영상 프로젝트를 대화형으로 만들고 파이프라인을 실행합니다."""

    console.print()
    console.print("[bold cyan]🎬 YouTube 영상 제작 파이프라인[/bold cyan]")
    console.print("[dim]질문에 답하면 프로젝트가 생성됩니다.[/dim]")
    console.print()

    # ── 질문 1: 주제 ──────────────────────────────────────────────
    topic = typer.prompt("📌 어떤 주제로 영상을 만들까요?").strip()
    while not topic:
        console.print("[red]주제를 입력해주세요.[/red]")
        topic = typer.prompt("📌 어떤 주제로 영상을 만들까요?").strip()

    # ── 질문 2: 채널 이름 ─────────────────────────────────────────
    channel = typer.prompt("📺 채널 이름은 무엇인가요?", default="My Channel").strip()

    # ── 질문 3: 카테고리 ──────────────────────────────────────────
    console.print("[dim]예: 역사, 과학, 미스터리, 요리, 여행, IT, 경제 ...[/dim]")
    niche = typer.prompt("🎯 카테고리를 알려주세요", default="General").strip()

    # 영상 길이는 1분(60초) 고정 — 쇼츠
    duration = 60

    # ── 확인 ──────────────────────────────────────────────────────
    console.print()
    console.print("[bold]── 입력 확인 ──────────────────────────────[/bold]")
    console.print(f"  주제    : [cyan]{topic}[/cyan]")
    console.print(f"  채널    : [cyan]{channel}[/cyan]")
    console.print(f"  카테고리: [cyan]{niche}[/cyan]")
    console.print(f"  길이    : [cyan]1분 쇼츠 (고정)[/cyan]")
    console.print()

    ok = typer.confirm("✅ 이대로 프로젝트를 생성할까요?", default=True)
    if not ok:
        console.print("[yellow]취소되었습니다.[/yellow]")
        raise typer.Exit()

    # ── 실행 ──────────────────────────────────────────────────────
    async def _run():
        container = create_app()
        await container.init()
        try:
            # 프로젝트 생성
            project = await container.orchestrator.projects.create(
                title_seed=topic,
                channel_name=channel,
                niche=niche,
                target_duration_sec=duration,
            )
            console.print(
                f"\n[green]✓[/green] 프로젝트 생성: [bold]{project.slug}[/bold]"
            )

            # intake
            intake = await container.orchestrator.run_stage(
                slug=project.slug,
                stage_name="intake",
            )
            if not intake.get("success"):
                console.print(f"[red]✗[/red] 워크스페이스 초기화 실패: {intake.get('error', 'unknown')}")
                return

            console.print("[green]✓[/green] 워크스페이스 초기화 완료")
            console.print()

            # ── 스테이지별 Progress ─────────────────────────────────
            await _run_pipeline_with_progress(
                container=container,
                slug=project.slug,
                niche=niche,
            )

        finally:
            await container.shutdown()

    asyncio.run(_run())


async def _run_pipeline_with_progress(container, slug: str, niche: str = "General") -> None:
    """스테이지 하나씩 실행하며 Rich 프로그레스 바로 진행 표시."""

    total = len(PIPELINE_STAGES)
    failed_stage: Optional[str] = None
    result_path: Optional[str] = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("[cyan]파이프라인 시작 중...", total=total)

        for i, stage_name in enumerate(PIPELINE_STAGES):
            label = STAGE_LABELS.get(stage_name, stage_name)
            progress.update(
                task,
                description=f"[cyan]{i + 1}/{total}[/cyan] {label} 진행 중...",
                completed=i,
            )

            result = await container.orchestrator.run_stage(
                slug=slug,
                stage_name=stage_name,
            )

            if result.get("success"):
                progress.update(
                    task,
                    description=f"[green]{i + 1}/{total}[/green] {label} [green]완료[/green]",
                    completed=i + 1,
                )
                # render 스테이지 완료 시 결과물 경로 수집
                if stage_name == "render":
                    result_data = result.get("result", "")
                    if isinstance(result_data, dict):
                        result_path = result_data.get("output_path")
                    elif isinstance(result_data, str) and result_data:
                        result_path = result_data
                    if not result_path:
                        # RESULT 폴더에서 추론
                        from app.settings import load_settings
                        settings, _ = load_settings()
                        result_path = str(Path(settings.workspace_root) / "RESULT")
            else:
                error = result.get("error", "알 수 없는 오류")
                progress.update(
                    task,
                    description=f"[red]{i + 1}/{total}[/red] {label} [red]실패[/red]",
                    completed=i + 1,
                )
                failed_stage = stage_name
                progress.stop()

                console.print()
                _print_error_panel(stage_name, error, slug)
                return

        # 전체 완료
        progress.update(task, description=f"[green]{total}/{total} 전체 완료[/green]", completed=total)

    console.print()
    _print_complete_banner(slug, result_path)


@app.command()
def resume(
    slug: str = typer.Argument(..., help="재시작할 프로젝트 슬러그"),
):
    """중단된 프로젝트를 마지막 실패 스테이지부터 재시작합니다."""

    console.print()
    console.print(f"[bold cyan]▶ 파이프라인 재시작: {slug}[/bold cyan]")
    console.print()

    async def _run():
        container = create_app()
        await container.init()
        try:
            project = await container.orchestrator.projects.get(slug)
            if not project:
                console.print("[red]✗[/red] 프로젝트를 찾을 수 없어요.")
                raise typer.Exit(1)

            # 완료된 스테이지를 파악 — 스테이지 디렉터리 존재 여부로 판단
            from app.settings import load_settings
            settings, _ = load_settings()
            ws = Path(settings.workspace_root) / "projects" / slug

            completed: set[str] = set()
            for stage in PIPELINE_STAGES:
                stage_dir = ws / stage
                # 스테이지 디렉터리가 있고 안에 파일이 있으면 완료로 간주
                if stage_dir.exists() and any(stage_dir.rglob("*.json")):
                    completed.add(stage)

            remaining = [s for s in PIPELINE_STAGES if s not in completed]

            if not remaining:
                console.print("[green]✓[/green] 이미 모든 스테이지가 완료됐어요.")
                _print_complete_banner(slug, str(Path(settings.workspace_root) / "RESULT"))
                return

            first_pending = remaining[0]
            label = STAGE_LABELS.get(first_pending, first_pending)
            console.print(f"  완료된 스테이지: [green]{', '.join(completed) or '없음'}[/green]")
            console.print(f"  재시작 지점    : [cyan]{label}[/cyan]")
            console.print()

            await _run_pipeline_with_progress(
                container=container,
                slug=slug,
            )

        finally:
            await container.shutdown()

    asyncio.run(_run())


@app.command()
def project_create(
    topic: str = typer.Option(..., help="Project topic/title seed"),
    channel: str = typer.Option("My Channel", help="Channel name"),
    niche: str = typer.Option("General", help="Content niche"),
    duration: int = typer.Option(480, help="Target duration in seconds"),
):
    """Create a new project (non-interactive). Use 'new' for guided setup."""
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
                error = result.get("error", "unknown")
                _print_error_panel(stage, error, slug)
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

            from app.settings import load_settings
            settings, _ = load_settings()
            ws = Path(settings.workspace_root) / "projects" / slug

            table = Table(title=f"Stage Status: {slug}", box=box.ROUNDED)
            table.add_column("스테이지", style="cyan")
            table.add_column("상태", style="white")
            table.add_column("산출물")

            for stage_name in PIPELINE_STAGES:
                label = STAGE_LABELS.get(stage_name, stage_name)
                stage_dir = ws / stage_name
                artifacts = list(stage_dir.rglob("*.json")) if stage_dir.exists() else []

                if artifacts:
                    status_text = Text("✓ 완료", style="green")
                    artifact_str = f"{len(artifacts)}개 파일"
                else:
                    status_text = Text("○ 대기", style="dim")
                    artifact_str = ""

                table.add_row(label, status_text, artifact_str)

            console.print(table)
            console.print(f"\n[dim]프로젝트 상태: {project.status.value}[/dim]")
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
        True, "--approve-all", help="Auto-approve non-upload checkpoints"
    ),
):
    """Run pipeline for a project."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            console.print(f"[cyan]Pipeline Run:[/cyan] {slug}")
            console.print(f"[cyan]Mode:[/cyan] {mode}")

            effective_from_stage = None if run_all else from_stage
            effective_until_stage = None if run_all else until_stage

            result = await container.orchestrator.run_pipeline(
                slug=slug,
                from_stage=effective_from_stage,
                until_stage=effective_until_stage,
                mode=mode,
                run_id=run_id,
                approve_all=approve_all,
            )

            console.print(f"[cyan]Run ID:[/cyan] {result.get('run_id', 'N/A')}")

            for stage_name, stage_result in result.get("stages", {}).items():
                if stage_result.get("success"):
                    console.print(f"  [green]✓[/green] {stage_name}: {stage_result.get('result', 'done')}")
                elif stage_result.get("status") == "awaiting_approval":
                    console.print(f"  [yellow]WAIT[/yellow] {stage_name}: {stage_result.get('message', 'awaiting approval')}")
                else:
                    error = stage_result.get("error", "failed")
                    console.print(f"  [red]✗[/red] {stage_name}: {error}")

            if result.get("completed"):
                console.print()
                _print_complete_banner(slug)
            else:
                console.print()
                console.print(f"[yellow]파이프라인이 중단됐어요. 재시도: python -m app.cli resume {slug}[/yellow]")
        finally:
            await container.shutdown()

    asyncio.run(_run())


# ============================================================================
# APPROVAL COMMANDS
# ============================================================================


@app.command()
def approvals_list(run_id: Optional[str] = typer.Argument(None, help="Optional run ID filter")):
    """List pending approvals."""
    async def _run():
        container = create_app()
        await container.init()
        try:
            if run_id:
                approvals = await container.orchestrator.approvals.list_pending(run_id)
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
