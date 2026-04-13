"""Logging configuration: JSON logs → file only, terminal shows WARNING+ as plain text."""

import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging(workspace_root: str = "workspace", level: str = "INFO") -> None:
    """Configure the root logging hierarchy for the pipeline.

    Strategy
    --------
    * ``app.*`` loggers write structured JSON to  <workspace>/logs/pipeline.log
      (rotating, 10 MB × 5 files).
    * Only WARNING and above are forwarded to the terminal, as compact plain
      text — no JSON noise for the user.
    * Third-party library loggers (httpx, openai, anthropic…) are silenced to
      WARNING to avoid cluttering the log file.

    Call this once at application startup (e.g., in ``main.py``).
    """
    log_dir = Path(workspace_root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline.log"

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # ── File handler: all app logs as JSON ───────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))  # already JSON

    # ── Console handler: WARNING+ as plain text ──────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )

    # ── app.* root logger ────────────────────────────────────────────────────
    app_logger = logging.getLogger("app")
    app_logger.setLevel(numeric_level)
    # Avoid duplicate handlers on hot-reload / multiple calls
    if not app_logger.handlers:
        app_logger.addHandler(file_handler)
        app_logger.addHandler(console_handler)
    app_logger.propagate = False  # don't bubble up to root logger

    # ── Quiet noisy third-party libs ─────────────────────────────────────────
    for noisy in ("httpx", "httpcore", "openai", "anthropic", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # ── Root logger: WARNING+ to console only (catches anything outside app.*) ─
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(console_handler)
    root.setLevel(logging.WARNING)
