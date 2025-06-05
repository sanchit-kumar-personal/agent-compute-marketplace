"""
Smoke tests for basic application functionality.
"""

from unittest.mock import patch
from payments.stripe_client import StripeClient
from payments.paypal_client import PayPalClient


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
@patch("paypalrestsdk.Payment.all")
def test_payment_clients(mock_paypal, mock_stripe, mock_settings):
    """Test payment client connections with mocked API calls."""
    # Configure mocks
    mock_stripe.return_value = {"id": "acct_test"}
    mock_paypal.return_value = [{"id": "PAY-test"}]

    # Test Stripe
    stripe_client = StripeClient(settings=mock_settings)
    assert stripe_client.test_connection() is True

    # Test PayPal
    paypal_client = PayPalClient(settings=mock_settings)
    assert paypal_client.test_connection() is True
