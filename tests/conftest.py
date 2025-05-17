"""Test configuration and fixtures."""

import os
import pytest
from fastapi.testclient import TestClient
from main import app, Settings
from unittest.mock import patch


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables before each test."""
    # Store original env vars
    original_env = dict(os.environ)

    # Set test environment variables
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///./test.db",
            "STRIPE_KEY": "sk_test_dummy",
            "PAYPAL_CLIENT_ID": "test_client_id",
            "PAYPAL_SECRET": "test_secret",
            "OPENAI_API_KEY": "sk-test-dummy",
            "APP_NAME": "Test Marketplace",
            "ENVIRONMENT": "development",
            "DEBUG": "true",
        }
    )

    yield

    # Restore original env vars
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_settings():
    return Settings(
        DATABASE_URL="sqlite:///./test.db",
        STRIPE_KEY="sk_test_mock",
        PAYPAL_CLIENT_ID="test_client_id",
        PAYPAL_SECRET="test_secret",
        OPENAI_API_KEY="sk-test-mock",
        APP_NAME="Test Marketplace",
        DEBUG=True,
        ENVIRONMENT="development",
    )


@pytest.fixture
def client(mock_settings):
    global _settings
    with patch("main._settings", mock_settings):
        with TestClient(app) as test_client:
            yield test_client
