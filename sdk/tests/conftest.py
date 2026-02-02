"""Test configuration and fixtures for SDK tests."""

import pytest


@pytest.fixture
def api_key() -> str:
    """Return a test API key."""
    return "aw_test_api_key_123456789012345678901"


@pytest.fixture
def base_url() -> str:
    """Return a test base URL."""
    return "http://localhost:8000"
