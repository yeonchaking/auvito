"""Slug generation utilities."""

import re
import unicodedata
import uuid


def create_slug(text: str) -> str:
    """Create a URL-safe slug from text.

    Supports Korean and other Unicode text by keeping non-ASCII word characters.
    Falls back to a short UUID-based slug if the result would be empty.
    """
    # Normalize unicode (NFC preserves Korean characters)
    text = unicodedata.normalize("NFC", text)

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and special characters with hyphens
    # Keep unicode word characters (letters, digits, underscore) including Korean
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "-", text)

    # Strip leading/trailing hyphens
    text = text.strip("-")

    # Fallback: if slug is empty (e.g. all special chars), use short UUID
    if not text:
        text = uuid.uuid4().hex[:8]

    return text
