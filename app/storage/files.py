"""File storage utilities."""

import json
from pathlib import Path
from typing import Any, Optional


class FileStorage:
    """File system storage helper."""

    @staticmethod
    async def save_json(path: str, data: Any, ensure_dir: bool = True) -> bool:
        """Save data to JSON file."""
        try:
            file_path = Path(path)
            if ensure_dir:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception:
            return False

    @staticmethod
    async def load_json(path: str) -> Optional[Any]:
        """Load data from JSON file."""
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    async def save_text(path: str, text: str, ensure_dir: bool = True) -> bool:
        """Save text to file."""
        try:
            file_path = Path(path)
            if ensure_dir:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w") as f:
                f.write(text)
            return True
        except Exception:
            return False

    @staticmethod
    async def load_text(path: str) -> Optional[str]:
        """Load text from file."""
        try:
            with open(path, "r") as f:
                return f.read()
        except Exception:
            return None

    @staticmethod
    async def file_exists(path: str) -> bool:
        """Check if file exists."""
        return Path(path).exists()

    @staticmethod
    async def ensure_dir(path: str) -> bool:
        """Ensure directory exists."""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False
