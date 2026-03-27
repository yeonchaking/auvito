"""Slug generation utilities."""

import re
import unicodedata


def create_slug(text: str) -> str:
    """Create a slug from text."""
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and special characters with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)

    # Strip leading/trailing hyphens
    text = text.strip("-")

    return text
