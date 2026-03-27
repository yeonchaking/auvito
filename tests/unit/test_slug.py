"""Tests for slug utilities."""

import pytest

from app.utils.slug import create_slug


def test_create_slug_basic():
    """Test basic slug creation."""
    assert create_slug("Hello World") == "hello-world"


def test_create_slug_special_chars():
    """Test slug with special characters."""
    assert create_slug("Hello, World!") == "hello-world"


def test_create_slug_unicode():
    """Test slug with unicode characters."""
    result = create_slug("주제")
    assert isinstance(result, str)


def test_create_slug_multiple_spaces():
    """Test slug with multiple spaces."""
    assert create_slug("Hello   World") == "hello-world"


def test_create_slug_leading_trailing():
    """Test slug removes leading/trailing hyphens."""
    assert create_slug("-hello-") == "hello"
