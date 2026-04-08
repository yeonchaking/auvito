"""Result collector: gathers final outputs into workspace/RESULT/{N}. {title}/"""

import re
import shutil
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Files to collect, in order: (source relative to project dir, dest filename)
_COLLECT_TARGETS = [
    ("06_render/draft.mp4",          "draft.mp4"),
    ("07_thumbnail/thumbnail.png",   "thumbnail.png"),
    ("03_voice/subtitles.ko.srt",    "subtitles.ko.srt"),
    ("03_voice/subtitles.en.srt",    "subtitles.en.srt"),   # optional
    ("02_script/final_script.md",    "script.md"),
]


def collect_results(workspace_root: str, project_slug: str, title: str) -> str:
    """Copy final artifacts into RESULT/{N}. {title}/.

    Args:
        workspace_root: Workspace root directory path
        project_slug: Project slug (folder name under projects/)
        title: Human-readable video title (used for folder name)

    Returns:
        Absolute path to the created result folder.
    """
    result_root = Path(workspace_root) / "RESULT"
    result_root.mkdir(parents=True, exist_ok=True)

    # ── Determine next folder number ─────────────────────────────────────────
    existing_numbers = []
    for p in result_root.iterdir():
        if p.is_dir():
            m = re.match(r"^(\d+)\.", p.name)
            if m:
                existing_numbers.append(int(m.group(1)))
    next_num = max(existing_numbers, default=0) + 1

    # ── Sanitize title for folder name ────────────────────────────────────────
    safe_title = re.sub(r'[\\/:*?"<>|]', "", title).strip()
    if len(safe_title) > 80:
        safe_title = safe_title[:80].rstrip()

    folder_name = f"{next_num}. {safe_title}"
    dest_dir = result_root / folder_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    # ── Copy files ────────────────────────────────────────────────────────────
    project_dir = Path(workspace_root) / "projects" / project_slug
    copied = []
    skipped = []

    for src_rel, dest_name in _COLLECT_TARGETS:
        src = project_dir / src_rel
        dest = dest_dir / dest_name

        if src.exists():
            shutil.copy2(str(src), str(dest))
            copied.append(dest_name)
            logger.info("Collected", file=dest_name, dest=str(dest_dir))
        else:
            skipped.append(dest_name)
            logger.debug("Skipped (not found)", file=dest_name, src=str(src))

    logger.info(
        "Result folder ready",
        folder=folder_name,
        copied=copied,
        skipped=skipped,
    )

    print(f"\n✓ RESULT 폴더 생성 완료: {dest_dir}")
    print(f"  수집된 파일: {', '.join(copied)}")
    if skipped:
        print(f"  건너뜀 (미생성): {', '.join(skipped)}")

    return str(dest_dir)
