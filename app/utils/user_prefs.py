"""User preferences — lightweight JSON store for CLI remembered values."""

import json
from pathlib import Path
from typing import Any, Optional


_PREFS_FILE = Path("workspace") / "user_prefs.json"


def _load() -> dict:
    try:
        if _PREFS_FILE.exists():
            return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(data: dict) -> None:
    _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get(key: str, default: Any = None) -> Any:
    """Get a stored preference value."""
    return _load().get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001
    """Store a preference value."""
    data = _load()
    data[key] = value
    _save(data)


def get_channel_name() -> Optional[str]:
    return get("channel_name")


def set_channel_name(name: str) -> None:
    set("channel_name", name)


def get_last_niche() -> Optional[str]:
    return get("last_niche")


def set_last_niche(niche: str) -> None:
    set("last_niche", niche)


def get_last_duration() -> Optional[int]:
    return get("last_duration")


def set_last_duration(sec: int) -> None:
    set("last_duration", sec)
