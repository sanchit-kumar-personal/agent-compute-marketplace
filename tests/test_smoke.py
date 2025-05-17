"""
Smoke tests for basic application functionality.
"""

from unittest.mock import patch
from payments.stripe_client import StripeClient
from payments.paypal_client import PayPalClient


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_name": "Test Marketplace"}


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
