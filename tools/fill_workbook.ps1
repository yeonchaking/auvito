param(
    [string]$TemplatePath = "C:\Users\AM11D\Documents\Claude\Projects\유튜브자동화\youtube_pipeline\tools\generated\통합문서_auvito.xlsx",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = $TemplatePath
}

$sheetPayloads = @{
    "프로젝트개요" = @{
        Columns = @("A", "B", "C", "D", "E", "F")
        StartRow = 3
        Rows = @(
            @("제품전략", "프로젝트명", "YouTube 영상 제작 자동화 파이프라인", "", "", "설계서 제목과 동일"),
            @("제품전략", "한 줄 소개", "주제 입력부터 YouTube 업로드까지 이어지는 한국어 faceless YouTube 콘텐츠 반자동 제작 파이프라인", "", "", "설계서 1장 한 줄 정의 기준"),
            @("범위", "Phase 1 범위", "Stage 0 ~ Stage 6(draft.mp4 생성)까지 구현", "", "", "설계서 15장 Phase 1 범위"),
            @("범위", "Phase 2 범위", "Stage 7(썸네일) / Stage 8(업로드)은 계약과 인터페이스만 유지하고 실제 구현은 보류", "", "", "설계서 15장 Phase 2 범위"),
            @("범위", "비목표", "GUI / 웹 서비스 / 다중 사용자 / 실시간 협업 / CapCut 내부 포맷 호환 / Shorts / 실사 브이로그", "", "", "설계서 1장 비목표"),
            @("운영원칙", "아티팩트 중심", "모든 단계의 결과는 파일(MD, JSON, 미디어)로 남기고 DB는 상태 추적용으로 사용", "", "", "설계서 1장 운영 원칙"),
            @("운영원칙", "승인 게이트", "주요 체크포인트에서 사람 승인을 받아야 다음 단계로 진행하며 기본 모드는 conditional", "", "", "설계서 2장, default.yaml"),
            @("운영원칙", "재개 가능", "단계 중단 후 재시작 가능하며 상태 판단의 authoritative source는 SQLite", "", "", "설계서 1장 운영 원칙"),
            @("운영원칙", "비용 통제", "모델 호출 횟수, 토큰, 이미지/비디오 수, 프로젝트별 총 비용을 기록하고 예산 상한을 강제", "", "", "설계서 1장, 9장"),
            @("기술", "현재 코드 의존성", "Typer, Pydantic, httpx, aiosqlite, Jinja2, edge-tts, Pillow, python-dotenv, PyYAML, Rich", "", "", "pyproject.toml 기준"),
            @("제약", "외부 의존성", "Anthropic/OpenAI/YouTube provider, Edge TTS, FFmpeg, Pillow, SQLite 기반 로컬 실행 환경 의존", "", "", "설계서와 현재 코드 기준")
        )
    }
    "개정이력" = @{
        Columns = @("A", "B", "C", "D", "E", "F", "G")
        StartRow = 3
        Rows = @(
            @("v0.1", "2026-03-28", "AM11D/Codex", "신규", "현재 프로젝트 코드와 종합 기술 설계서를 기준으로 통합문서 초안 작성", "전체 문서", ""),
            @("v0.2", "2026-03-28", "AM11D/Codex", "수정", "예시성/창작성 데이터 제거 후 프로젝트와 설계서에 있는 사실만 반영하도록 재정리", "프로젝트개요, 기능정의, 요구사항, 일정, 리스크", ""),
            @("v0.3", "2026-03-28", "AM11D/Codex", "수정", "Stage 6 렌더 일부 구현과 FFmpeg 임시경로 변경 사항을 현재 코드 기준으로 반영", "기능정의, 요구사항, 이슈·리스크, 테스트케이스", "")
        )
    }
    "기능정의 - 상세" = @{
        Columns = @("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M")
        StartRow = 3
        Rows = @(
            @("F-PROJ-001", "오케스트레이션", "프로젝트 관리", "프로젝트 생성/조회/삭제", "project_create, project_list, project_show, project_delete 명령과 ProjectManager CRUD", "app/cli.py, app/core/project_manager.py, app/storage/sqlite.py에 관련 코드가 존재", "CLI 사용자", "", "일부구현", "SCR-001", "REQ-PROJ-001", "", "현재 코드 기준"),
            @("F-EXEC-001", "오케스트레이션", "실행 제어", "Stage 실행 상태와 실행 모드 결정", "execution_digest, skip/resume/overwrite, stage run 상태 기록", "app/core/stage_executor.py에 결정 로직과 상태 전이 메서드가 구현되어 있음", "CLI 사용자", "", "일부구현", "SCR-002", "REQ-EXEC-001, REQ-COST-001", "", "현재 코드 기준"),
            @("F-GOV-001", "거버넌스", "승인/비용/품질", "ApprovalService / CostGuardrail / QualityGateRunner", "승인 체크포인트, 비용 가드레일, 자동 품질 검증", "app/core/approval_service.py, app/core/cost_guardrail.py, app/core/quality_gate.py에 관련 코드가 존재", "CLI 사용자", "", "일부구현", "SCR-004", "REQ-GOV-001, REQ-COST-001", "", "현재 코드 기준"),
            @("F-BENCH-001", "Stage", "벤치마킹", "BenchmarkReport 계약과 stage/provider 인터페이스", "BenchmarkReport 계약, ResearchProvider, benchmark stage 골격", "app/domain/contracts.py, app/providers/research.py, app/stages/stage1_benchmark.py 기준", "CLI 사용자", "", "골격구현", "SCR-003", "REQ-BENCH-001", "", "현재 코드 기준"),
            @("F-SCRIPT-001", "Stage", "대본", "ScriptContract와 script 승인 게이트", "ScriptContract 계약, NarrativeProvider의 script 메서드, script checkpoint 설계", "app/domain/contracts.py, app/providers/narrative.py, app/stages/stage2_script.py, app/config/default.yaml 기준", "CLI 사용자", "", "골격구현", "SCR-004", "REQ-SCRIPT-001, REQ-GOV-001", "", "현재 코드 기준"),
            @("F-MEDIA-001", "Stage", "음성/스토리보드/에셋/렌더", "Narration/Storyboard/Asset/Render 계약 체인", "NarrationContract, StoryboardContract, AssetManifestContract, RenderPlanContract와 Stage 6 렌더 코드", "app/domain/contracts.py, app/providers/*.py, app/services/ffmpeg_service.py, app/services/pillow_service.py, app/stages/stage3_voice.py ~ stage6_render.py 기준. Stage 3~5는 골격이고 Stage 6 렌더는 일부 구현 상태", "CLI 사용자", "", "일부구현", "SCR-005, SCR-006", "REQ-VOICE-001, REQ-VISUAL-001", "", "현재 코드 기준")
        )
    }
    "화면기능매핑테이블" = @{
        Columns = @("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N")
        StartRow = 3
        Rows = @(
            @("SCR-001", "CLI", "프로젝트", "", "", "", "프로젝트 관리 명령", "명령", "project slug를 생성하거나 조회/삭제할 때", "yt project create / list / show / delete", "F-PROJ-001", "REQ-PROJ-001", "", "현재 CLI 기준"),
            @("SCR-002", "CLI", "실행", "파이프라인", "", "", "단계 실행 및 파이프라인 실행 명령", "명령", "특정 stage 또는 pipeline run을 제어할 때", "yt stage run / yt pipeline run", "F-EXEC-001", "REQ-EXEC-001, REQ-COST-001", "", "현재 CLI 기준"),
            @("SCR-003", "작업공간", "01_benchmark", "", "", "", "벤치마킹 산출물 검토", "산출물", "BenchmarkReport와 관련 산출물을 확인할 때", "benchmark_report.json / md / keyword bank", "F-BENCH-001", "REQ-BENCH-001", "", "설계서 워크스페이스 구조 기준"),
            @("SCR-004", "CLI", "승인", "검토", "", "", "승인 명령 및 checkpoint 처리", "명령", "approval_id 기준 승인/거절을 수행할 때", "yt approvals list / approve / reject", "F-GOV-001, F-SCRIPT-001", "REQ-GOV-001", "", "현재 CLI와 설계서 기준"),
            @("SCR-005", "작업공간", "03_voice", "", "", "", "음성/자막 산출물 검토", "산출물", "NarrationContract와 narration/subtitles 산출물을 확인할 때", "narration.wav / subtitles.srt / narration_contract.json", "F-MEDIA-001", "REQ-VOICE-001", "", "설계서 워크스페이스 구조 기준"),
            @("SCR-006", "작업공간", "04_storyboard", "05_assets", "06_render", "", "스토리보드/에셋/렌더 산출물 검토", "산출물", "Storyboard, AssetManifest, RenderPlan과 draft 결과를 확인할 때", "storyboard_contract.json / asset_manifest.json / render_plan.json / draft.mp4", "F-MEDIA-001", "REQ-VISUAL-001", "", "render_plan.json / draft.mp4는 현재 Stage 6 코드 기준")
        )
    }
    "요구사항정의서" = @{
        Columns = @("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M")
        StartRow = 3
        Rows = @(
            @("REQ-PROJ-001", "기능", "프로젝트 생성/조회/삭제 명령 제공", "", "F-PROJ-001", "SCR-001", "현재 코드에는 project create, list, show, delete 명령과 ProjectManager CRUD가 존재한다.", "app/cli.py, app/core/project_manager.py, app/storage/sqlite.py", "프로젝트 slug와 상태를 저장하고 동일 slug로 조회/삭제 가능", "", "CLI 앱", "일부구현", ""),
            @("REQ-EXEC-001", "기능", "단계 실행 모드와 상태 전이 관리", "", "F-EXEC-001", "SCR-002", "StageExecutor는 skip/resume/overwrite 판단과 stage run 상태 전이 메서드를 제공한다.", "run_id, stage_name, execution_digest, requested_mode", "PENDING/RUNNING/SUCCEEDED/FAILED/PARTIAL/SKIPPED 상태를 저장하는 메서드 존재", "", "파이프라인", "일부구현", ""),
            @("REQ-GOV-001", "정책", "승인 체크포인트와 품질/비용 가드레일 유지", "", "F-GOV-001", "SCR-004", "설계서와 default.yaml에는 script, storyboard, assets_over_usd, thumbnail, upload 체크포인트와 cost_guardrail 정책이 정의되어 있다.", "app/core/approval_service.py, app/core/cost_guardrail.py, app/core/quality_gate.py, app/config/default.yaml", "approval, cost, quality 관련 코드와 설정 파일이 존재", "", "파이프라인", "일부구현", ""),
            @("REQ-BENCH-001", "기능", "벤치마킹 단계는 BenchmarkReport 계약을 사용", "", "F-BENCH-001", "SCR-003", "BenchmarkReport 계약, ResearchProvider 인터페이스, benchmark stage 파일이 현재 프로젝트에 존재한다.", "app/domain/contracts.py, app/providers/research.py, app/stages/stage1_benchmark.py", "벤치마킹 출력 계약과 stage/provider 골격이 존재", "", "파이프라인", "골격구현", ""),
            @("REQ-SCRIPT-001", "기능", "대본 단계는 ScriptContract 계약을 사용", "", "F-SCRIPT-001", "SCR-004", "ScriptContract 계약과 NarrativeProvider의 script 관련 인터페이스가 존재하고 script checkpoint 설계가 문서와 설정에 반영되어 있다.", "app/domain/contracts.py, app/providers/narrative.py, app/config/default.yaml", "대본 계약과 승인 체크포인트 정의 존재", "", "파이프라인", "골격구현", ""),
            @("REQ-VOICE-001", "기능", "음성 단계는 NarrationContract와 자막 산출물을 사용", "", "F-MEDIA-001", "SCR-005", "NarrationContract, TTS/STT provider 인터페이스, voice stage 파일이 현재 프로젝트에 존재한다.", "app/domain/contracts.py, app/providers/tts.py, app/providers/stt.py, app/stages/stage3_voice.py", "나레이션 계약과 관련 provider/stage 골격이 존재", "", "파이프라인", "골격구현", ""),
            @("REQ-VISUAL-001", "기능", "스토리보드/에셋/렌더 단계는 계약 기반 체인을 사용", "", "F-MEDIA-001", "SCR-006", "StoryboardContract, AssetManifestContract, RenderPlanContract가 정의되어 있고 Stage 6에는 FFmpeg 기반 draft 렌더 코드가 존재한다.", "app/domain/contracts.py, app/providers/asset.py, app/services/ffmpeg_service.py, app/services/pillow_service.py, app/stages/stage4_storyboard.py ~ stage6_render.py", "Stage 4~5 관련 파일 존재, Stage 6은 draft.mp4 / render_plan.json 생성 로직 존재", "", "파이프라인", "일부구현", ""),
            @("REQ-COST-001", "비기능", "비용 통제 설정과 검사 로직 존재", "", "F-EXEC-001, F-GOV-001", "SCR-002", "default.yaml에는 stage별 hard cap과 provider limit가 정의되어 있고 CostGuardrail 클래스가 이를 읽는다.", "app/config/default.yaml, app/core/cost_guardrail.py", "cost_guardrail 설정과 검사 코드 존재", "", "파이프라인", "일부구현", "")
        )
    }
    "일정·마일스톤" = @{
        Columns = @("A", "B", "C", "D", "E", "F", "G", "H", "I")
        StartRow = 3
        Rows = @(
            @("MS-01", "Phase 1", "Stage 0 ~ Stage 6(draft.mp4 생성)까지 구현", "", "", "설계서 15장 Phase 1 범위", "진행중", "F-PROJ-001, F-EXEC-001, F-BENCH-001, F-SCRIPT-001, F-MEDIA-001", ""),
            @("MS-02", "Phase 2", "썸네일, YouTube 업로드, Sora 비디오 생성, 비용 리포트 UI, final.mp4", "", "", "설계서 15장 Phase 2 범위", "", "", ""),
            @("MS-03", "Phase 3", "웹 UI, 다중 채널 프리셋, 템플릿 반복 제작, A/B 썸네일, BGM", "", "", "설계서 15장 Phase 3 범위", "", "", "")
        )
    }
    "이슈·리스크" = @{
        Columns = @("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")
        StartRow = 3
        Rows = @(
            @("RISK-001", "현재 코드", "pydantic-settings 의존성 누락", "app/settings.py는 pydantic_settings.BaseSettings를 import하지만 pyproject.toml 기본 의존성에는 pydantic-settings가 없다.", "", "", "미정", "", "", "app/settings.py, pyproject.toml"),
            @("RISK-002", "현재 코드", "DB init 중복 호출", "AppContainer.init()와 PipelineOrchestrator.initialize()가 모두 self.db.init()를 호출한다.", "", "", "미정", "", "", "app/main.py, app/core/orchestrator.py"),
            @("RISK-003", "현재 코드", "Artifact 저장/조회 형식 불일치", "Artifact 모델의 list/dict 필드와 SQLite 저장/조회 형식이 직접 대응하지 않아 조회 시 불일치 가능성이 있다.", "", "", "미정", "", "", "app/domain/models.py, app/storage/sqlite.py, app/core/artifact_registry.py"),
            @("RISK-004", "현재 코드", "fake provider 일부의 /tmp 경로 사용", "FFmpegService는 tempfile로 전환되었으나 fake provider 일부는 여전히 /tmp 경로를 사용한다.", "", "", "미정", "", "", "app/services/ffmpeg_service.py, app/providers/fake.py")
        )
    }
    "테스트케이스" = @{
        Columns = @("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")
        StartRow = 3
        Rows = @(
            @("TC-001", "REQ-PROJ-001", "SCR-001", "프로젝트 생성 후 slug와 상태 저장 확인", "유효한 topic 입력, DB 경로 접근 가능", "yt project create --topic '테스트 주제'", "project가 생성되고 slug, status, created_at이 저장된다.", "", "", "설계서 검증 방법 1번 기반"),
            @("TC-002", "REQ-EXEC-001", "SCR-002", "동일 execution_digest에서 실행 모드 결정 확인", "이전 stage run 이력 존재", "skip / resume / overwrite 조합으로 stage executor 호출", "mode와 이전 상태에 따라 skip, resume, execute 결정이 달라진다.", "", "", "설계서 검증 방법 6,7번 기반"),
            @("TC-003", "REQ-GOV-001", "SCR-004", "approval 상태 전이 확인", "approval_id 존재", "yt approve <approval_id> 또는 yt reject <approval_id>", "approval 상태가 APPROVED 또는 REJECTED로 저장된다.", "", "", "설계서 검증 방법 3번 기반"),
            @("TC-004", "REQ-BENCH-001", "SCR-003", "BenchmarkReport 계약 생성 확인", "benchmark stage 실행 가능 상태", "yt stage run <slug> benchmark", "BenchmarkReport contract 파일과 quality gate 검증 대상이 생성된다.", "", "", "설계서 검증 방법 2번 기반"),
            @("TC-005", "REQ-VOICE-001", "SCR-005", "NarrationContract와 자막 산출물 생성 확인", "voice stage 실행 가능 상태", "voice stage 실행", "narration.wav, subtitles.srt, NarrationContract가 생성된다.", "", "", "설계서 7장 stage 설명 기반"),
            @("TC-006", "REQ-VISUAL-001", "SCR-006", "RenderStage 입력 계약 기반 draft 산출 확인", "NarrationContract, StoryboardContract, AssetManifestContract와 출력 경로가 준비됨", "RenderStage execute 호출", "06_render에 render_plan.json과 draft.mp4가 생성되고 RenderPlanContract가 반환된다.", "", "", "app/stages/stage6_render.py 현재 코드 기준")
        )
    }
}

function Get-SheetMap {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkbookRoot
    )

    $utf8 = [System.Text.Encoding]::UTF8
    [xml]$workbook = [System.IO.File]::ReadAllText((Join-Path $WorkbookRoot "xl\workbook.xml"), $utf8)
    [xml]$rels = [System.IO.File]::ReadAllText((Join-Path $WorkbookRoot "xl\_rels\workbook.xml.rels"), $utf8)

    $wbNs = New-Object System.Xml.XmlNamespaceManager($workbook.NameTable)
    $wbNs.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

    $relNs = New-Object System.Xml.XmlNamespaceManager($rels.NameTable)
    $relNs.AddNamespace("r", "http://schemas.openxmlformats.org/package/2006/relationships")

    $map = @{}
    foreach ($sheet in $workbook.SelectNodes("//x:sheets/x:sheet", $wbNs)) {
        $rid = $sheet.GetAttribute("id", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
        $relationship = $rels.SelectSingleNode("//r:Relationship[@Id='$rid']", $relNs)
        $target = $relationship.Target.Replace("/", "\")
        if ($target.StartsWith("xl\")) {
            $target = $target.Substring(3)
        }
        $map[$sheet.name] = Join-Path $WorkbookRoot ("xl\" + $target)
    }

    return $map
}

function Set-InlineStringCell {
    param(
        [Parameter(Mandatory = $true)]
        [xml]$SheetXml,
        [Parameter(Mandatory = $true)]
        [System.Xml.XmlNamespaceManager]$Ns,
        [Parameter(Mandatory = $true)]
        [string]$CellRef,
        [AllowNull()]
        [string]$Value
    )

    $cell = $SheetXml.SelectSingleNode("//x:c[@r='$CellRef']", $Ns)
    if (-not $cell) {
        throw "Cell not found: $CellRef"
    }

    while ($cell.FirstChild) {
        [void]$cell.RemoveChild($cell.FirstChild)
    }

    if ($cell.HasAttribute("t")) {
        $cell.RemoveAttribute("t")
    }

    if ([string]::IsNullOrEmpty($Value)) {
        return
    }

    $cell.SetAttribute("t", "inlineStr")
    $inline = $SheetXml.CreateElement("is", $Ns.LookupNamespace("x"))
    $text = $SheetXml.CreateElement("t", $Ns.LookupNamespace("x"))

    if ($Value.StartsWith(" ") -or $Value.EndsWith(" ") -or $Value.Contains("`n")) {
        $text.SetAttribute("space", "http://www.w3.org/XML/1998/namespace", "preserve")
    }

    $text.InnerText = $Value
    [void]$inline.AppendChild($text)
    [void]$cell.AppendChild($inline)
}

function Write-SheetRows {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SheetPath,
        [Parameter(Mandatory = $true)]
        [hashtable]$Payload
    )

    $utf8 = [System.Text.Encoding]::UTF8
    [xml]$sheetXml = [System.IO.File]::ReadAllText($SheetPath, $utf8)
    $ns = New-Object System.Xml.XmlNamespaceManager($sheetXml.NameTable)
    $ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

    $columns = $Payload.Columns
    $rowNumber = [int]$Payload.StartRow

    foreach ($row in $Payload.Rows) {
        for ($i = 0; $i -lt $columns.Count; $i++) {
            $cellRef = "{0}{1}" -f $columns[$i], $rowNumber
            $value = if ($i -lt $row.Count) { [string]$row[$i] } else { "" }
            Set-InlineStringCell -SheetXml $sheetXml -Ns $ns -CellRef $cellRef -Value $value
        }
        $rowNumber++
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($SheetPath, $sheetXml.OuterXml, $utf8NoBom)
}

function New-XlsxArchive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    $fileStream = [System.IO.File]::Open($DestinationPath, [System.IO.FileMode]::Create)
    try {
        $zip = New-Object System.IO.Compression.ZipArchive(
            $fileStream,
            [System.IO.Compression.ZipArchiveMode]::Create,
            $false
        )
        try {
            Get-ChildItem -LiteralPath $SourceDir -Recurse -File | ForEach-Object {
                $relativePath = $_.FullName.Substring($SourceDir.Length).TrimStart("\", "/")
                $entryName = $relativePath -replace "\\", "/"
                $entry = $zip.CreateEntry(
                    $entryName,
                    [System.IO.Compression.CompressionLevel]::Optimal
                )

                $inputStream = [System.IO.File]::OpenRead($_.FullName)
                $entryStream = $entry.Open()
                try {
                    $inputStream.CopyTo($entryStream)
                }
                finally {
                    $entryStream.Dispose()
                    $inputStream.Dispose()
                }
            }
        }
        finally {
            $zip.Dispose()
        }
    }
    finally {
        $fileStream.Dispose()
    }
}

$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
}
else {
    [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputPath))
}

$outputDir = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$scratchRoot = Join-Path $PSScriptRoot (".tmp_workbook_" + [guid]::NewGuid().ToString("N"))
$extractDir = Join-Path $scratchRoot "extract"
New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($TemplatePath, $extractDir)

    $sheetMap = Get-SheetMap -WorkbookRoot $extractDir

    foreach ($sheetName in $sheetPayloads.Keys) {
        Write-SheetRows -SheetPath $sheetMap[$sheetName] -Payload $sheetPayloads[$sheetName]
    }

    if (Test-Path -LiteralPath $resolvedOutput) {
        Remove-Item -LiteralPath $resolvedOutput -Force
    }

    New-XlsxArchive -SourceDir $extractDir -DestinationPath $resolvedOutput
    Write-Output $resolvedOutput
}
finally {
    if (Test-Path -LiteralPath $scratchRoot) {
        Remove-Item -LiteralPath $scratchRoot -Recurse -Force
    }
}
