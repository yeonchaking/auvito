"""JSON repair utilities for malformed LLM outputs."""

import json
import re


def repair_json(text: str) -> str:
    """Attempt to repair malformed JSON."""
    # Remove markdown code blocks
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Try parsing as-is first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Fix common issues
    # Replace single quotes with double quotes
    text = text.replace("'", '"')

    # Fix unquoted keys
    text = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)

    # Fix trailing commas
    text = re.sub(r',\s*([}\]])', r"\1", text)

    # Try parsing again
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Last resort: try to extract valid JSON object/array
    match = re.search(r"[\{|\[].*[\}|\]]", text, re.DOTALL)
    if match:
        return match.group(0)

    return text
