"""
Simple smoke tests to verify basic functionality.
"""

from unittest.mock import MagicMock, patch


def test_app_startup(client):
    """Test that the application starts up properly."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    # Check the actual structure returned by healthz
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "database" in data
    assert "environment" in data


def test_openapi_available(client):
    """Test that OpenAPI documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200


@patch("stripe.Account.retrieve")
def test_payment_clients(mock_stripe, mock_settings, test_db_session):
    """Test payment service initialization and health checks."""
    # Configure mocks
    mock_stripe.return_value = {"id": "acct_test"}

    # Create mock settings
    from core.settings import Settings

    settings = Settings(STRIPE_API_KEY="test_key")

    # Test Stripe
    from payments.stripe_service import StripeService

    stripe_service = StripeService(db=test_db_session, settings=settings)
    assert stripe_service.test_connection() is True

    # Clear PayPal token cache before test
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    # Mock PayPal token request to avoid real API calls
    with patch("payments.paypal_service.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_token"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Test PayPal
        from payments.paypal_service import PayPalService

        paypal_service = PayPalService()
        token = paypal_service._token()

        # Use the actual token value that would be returned
        assert token == "test_token"


def test_database_connection(test_db_session):
    """Test that database connection works."""
    # Simple test to verify database session works
    from db.models import Quote, QuoteStatus

    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        status=QuoteStatus.pending,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    # Verify quote was saved
    retrieved = test_db_session.query(Quote).filter_by(buyer_id="test_buyer").first()
    assert retrieved is not None
    assert retrieved.resource_type == "GPU"
