"""
Comprehensive Stripe payment tests for MVP architecture.
"""

import pytest
from unittest.mock import MagicMock, patch

from db.models import (
    Quote,
    QuoteStatus,
    Transaction,
    TransactionStatus,
    PaymentProvider,
)
from payments.stripe_service import StripeService, StripeError

BASE = "/api/v1"


def test_stripe_service_initialization(test_db_session, mock_settings):
    """Test Stripe service initialization."""
    from core.settings import Settings

    settings = Settings(STRIPE_API_KEY="test_key")

    service = StripeService(db=test_db_session, settings=settings)
    assert service.db == test_db_session
    # Note: settings is not stored as an attribute, only used to set stripe.api_key


@patch("payments.stripe_service.stripe.Account.retrieve")
def test_stripe_service_test_connection_success(
    mock_retrieve, test_db_session, mock_settings
):
    """Test successful Stripe connection test."""
    from core.settings import Settings

    settings = Settings(STRIPE_API_KEY="test_key")

    # Mock successful account retrieval
    mock_retrieve.return_value = {"id": "acct_test"}

    service = StripeService(db=test_db_session, settings=settings)
    result = service.test_connection()

    assert result is True
    mock_retrieve.assert_called_once()


@patch("payments.stripe_service.stripe.Account.retrieve")
def test_stripe_service_test_connection_failure(
    mock_retrieve, test_db_session, mock_settings
):
    """Test failed Stripe connection test."""
    from core.settings import Settings

    settings = Settings(STRIPE_API_KEY="test_key")

    # Mock account retrieval failure
    mock_retrieve.side_effect = Exception("Stripe connection failed")

    service = StripeService(db=test_db_session, settings=settings)
    result = service.test_connection()

    assert result is False


@pytest.mark.asyncio
async def test_stripe_payment_intent_creation(client, test_db_session):
    """Test Stripe PaymentIntent creation - MVP always succeeds."""
    # Create an accepted quote
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=100.0,
        status=QuoteStatus.accepted,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    # Mock Stripe PaymentIntent creation
    with patch("payments.stripe_service.stripe.PaymentIntent.create") as mock_create:
        mock_intent = MagicMock()
        mock_intent.id = "pi_test_123"
        mock_intent.client_secret = "pi_test_123_secret_test"
        mock_create.return_value = mock_intent

        response = client.post(
            f"{BASE}/quotes/{quote.id}/payments?provider=stripe",
        )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["provider"] == "stripe"
    assert data["client_secret"] == "pi_test_123_secret_test"
    assert data["payment_intent_id"] == "pi_test_123"
    assert data["amount"] == 100.0

    # Verify transaction was created and quote updated (demo behavior)
    test_db_session.refresh(quote)
    assert quote.status == QuoteStatus.paid  # Demo: quote marked as paid immediately

    transaction = (
        test_db_session.query(Transaction).filter_by(quote_id=quote.id).first()
    )
    assert transaction is not None
    assert transaction.provider == PaymentProvider.stripe
    assert transaction.provider_id == "pi_test_123"
    assert (
        transaction.status == TransactionStatus.succeeded
    )  # Demo: transaction marked as succeeded immediately


@pytest.mark.asyncio
async def test_stripe_payment_intent_stripe_error(test_db_session, mock_settings):
    """Test Stripe PaymentIntent creation with Stripe API error."""
    from core.settings import Settings
    import stripe

    settings = Settings(STRIPE_API_KEY="test_key")
    service = StripeService(db=test_db_session, settings=settings)

    # Create test quote
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=100.0,
        status=QuoteStatus.accepted,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    # Mock Stripe error
    with patch("payments.stripe_service.stripe.PaymentIntent.create") as mock_create:
        mock_create.side_effect = stripe.error.StripeError("API error")

        with pytest.raises(StripeError, match="API error"):
            await service.create_payment_intent(quote)


@pytest.mark.asyncio
async def test_stripe_payment_intent_generic_error(test_db_session, mock_settings):
    """Test Stripe PaymentIntent creation with generic error."""
    from core.settings import Settings

    settings = Settings(STRIPE_API_KEY="test_key")
    service = StripeService(db=test_db_session, settings=settings)

    # Create test quote
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=100.0,
        status=QuoteStatus.accepted,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    # Mock generic error
    with patch("payments.stripe_service.stripe.PaymentIntent.create") as mock_create:
        mock_create.side_effect = Exception("Network error")

        with pytest.raises(StripeError, match="Network error"):
            await service.create_payment_intent(quote)


@pytest.mark.asyncio
async def test_stripe_duplicate_payment_prevention(client, test_db_session):
    """Test that duplicate Stripe payments are prevented."""
    # Create an accepted quote
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=100.0,
        status=QuoteStatus.accepted,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    # Create first payment successfully
    with patch("payments.stripe_service.stripe.PaymentIntent.create") as mock_create:
        mock_intent = MagicMock()
        mock_intent.id = "pi_first_payment"
        mock_intent.client_secret = "pi_first_payment_secret"
        mock_create.return_value = mock_intent

        response1 = client.post(
            f"{BASE}/quotes/{quote.id}/payments?provider=stripe",
        )

    assert response1.status_code == 200

    # Attempt second payment should fail with 409
    response2 = client.post(
        f"{BASE}/quotes/{quote.id}/payments?provider=stripe",
    )

    assert response2.status_code == 409
    assert "already has a payment transaction" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_stripe_auto_negotiate_integration(client):
    """Test Stripe integration with auto-negotiate flow."""
    # Create quote that will likely be accepted
    r = client.post(
        f"{BASE}/quotes/request",
        json={
            "buyer_id": "stripe_user",
            "resource_type": "CPU",
            "duration_hours": 2,
            "buyer_max_price": 20.0,  # High budget to encourage acceptance
        },
    )
    assert r.status_code == 201
    quote_id = r.json()["quote_id"]

    # Mock Stripe for auto-negotiate
    with patch("payments.stripe_service.stripe.PaymentIntent.create") as mock_create:
        mock_intent = MagicMock()
        mock_intent.id = "pi_auto_negotiate"
        mock_intent.client_secret = "pi_auto_negotiate_secret"
        mock_create.return_value = mock_intent

        # Run auto-negotiation with Stripe
        res = client.post(f"{BASE}/quotes/{quote_id}/negotiate/auto?provider=stripe")
        assert res.status_code == 200
        quote = res.json()

        # In MVP, either negotiation fails (rejected) or Stripe succeeds (paid)
        assert quote["status"] in [QuoteStatus.paid.value, QuoteStatus.rejected.value]

        # If payment was processed, verify transaction details
        if quote["status"] == QuoteStatus.paid.value:
            transactions = quote.get("transactions", [])
            assert len(transactions) > 0
            tx = transactions[0]
            assert tx["provider"] == PaymentProvider.stripe.value
            assert tx["status"] == TransactionStatus.succeeded.value


@pytest.mark.asyncio
async def test_stripe_api_failure(client, test_db_session):
    """Test Stripe API failure handling."""
    # Create an accepted quote
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=50.0,
        status=QuoteStatus.accepted,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    # Mock Stripe to raise an exception
    with patch("payments.stripe_service.stripe.PaymentIntent.create") as mock_create:
        mock_create.side_effect = Exception("Stripe API unavailable")

        response = client.post(
            f"{BASE}/quotes/{quote.id}/payments?provider=stripe",
        )

    # Should return 500 for API failures
    assert response.status_code == 500
    assert "Stripe API unavailable" in response.json()["detail"]


def test_stripe_service_initialization_without_settings(test_db_session):
    """Test Stripe service initialization without settings."""
    service = StripeService(db=test_db_session, settings=None)
    assert service.db == test_db_session


def test_stripe_service_initialization_with_faulty_settings(test_db_session):
    """Test Stripe service initialization with settings that can't be accessed."""
    # Mock a settings object that raises errors when accessing STRIPE_API_KEY
    faulty_settings = MagicMock()
    faulty_settings.STRIPE_API_KEY = MagicMock(side_effect=AttributeError("No API key"))

    # This should fall back to environment variable without raising an exception
    service = StripeService(db=test_db_session, settings=faulty_settings)
    assert service.db == test_db_session
