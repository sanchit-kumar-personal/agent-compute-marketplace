"""
Smoke tests for basic application functionality.
"""

from unittest.mock import patch
from payments.stripe_service import StripeService
from payments.paypal_service import PayPalService
from core.settings import Settings


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Agent Compute Marketplace"


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()

    # Check required fields
    assert data["status"] == "ok"
    assert data["app_name"] == "Test Marketplace"

    # Check optional fields that were added in the PostgreSQL transition
    assert "database" in data  # Should be either "SQLite" or "PostgreSQL"
    assert "environment" in data  # Should be "development"

    # Verify database type is one of the expected values
    assert data["database"] in ["SQLite", "PostgreSQL"]
    assert data["environment"] == "development"


@patch("stripe.Account.retrieve")
@patch("requests.post")
def test_payment_clients(mock_paypal_post, mock_stripe, mock_settings, test_db_session):
    """Test payment client connections with mocked API calls."""
    # Configure mocks
    mock_stripe.return_value = {"id": "acct_test"}
    mock_paypal_post.return_value.json.return_value = {"access_token": "test_token"}
    mock_paypal_post.return_value.raise_for_status.return_value = None

    # Create mock settings
    settings = Settings(STRIPE_API_KEY="test_key")

    # Test Stripe
    stripe_service = StripeService(db=test_db_session, settings=settings)
    assert stripe_service.test_connection() is True

    # Test PayPal
    paypal_service = PayPalService()
    token = paypal_service._token()
    assert token == "test_token"
