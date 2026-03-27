"""Tests for JSON repair utilities."""

import json
import pytest

from app.utils.json_repair import repair_json


def test_repair_json_valid():
    """Test valid JSON is unchanged."""
    valid = '{"key": "value"}'
    assert json.loads(repair_json(valid)) == {"key": "value"}


def test_repair_json_single_quotes():
    """Test single quotes are converted."""
    malformed = "{'key': 'value'}"
    result = repair_json(malformed)
    assert json.loads(result) == {"key": "value"}


def test_repair_json_unquoted_keys():
    """Test unquoted keys are quoted."""
    malformed = "{key: 'value'}"
    result = repair_json(malformed)
    assert json.loads(result) == {"key": "value"}


def test_repair_json_trailing_commas():
    """Test trailing commas are removed."""
    malformed = '{"key": "value",}'
    result = repair_json(malformed)
    assert json.loads(result) == {"key": "value"}


def test_repair_json_markdown_block():
    """Test markdown code blocks are stripped."""
    markdown = '```json\n{"key": "value"}\n```'
    result = repair_json(markdown)
    assert json.loads(result) == {"key": "value"}
