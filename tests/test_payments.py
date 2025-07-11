"""
Tests for payment functionality
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import stripe

from db.models import (
    PaymentProvider,
    Quote,
    QuoteStatus,
    Transaction,
    TransactionStatus,
)


@pytest.fixture
def mock_stripe():
    """Mock Stripe API for testing."""
    with patch("stripe.PaymentIntent") as mock:
        mock.create.return_value = type(
            "PaymentIntent", (), {"id": "pi_mock", "status": "requires_payment_method"}
        )()
        yield mock


def test_create_payment_for_accepted_quote(client, test_db_session, mock_stripe):
    # Create a quote in accepted status
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=100.0,
        buyer_max_price=100.0,
        status=QuoteStatus.accepted,
        created_at=datetime.now(UTC),
        negotiation_log="[]",
    )
    test_db_session.add(quote)
    test_db_session.commit()
    test_db_session.refresh(quote)

    # Create payment using dedicated payment endpoint
    with patch("stripe.PaymentIntent.create") as mock_create:
        mock_create.return_value.id = "pi_mock"
        response = client.post(f"/quotes/{quote.id}/payments")
        assert response.status_code == 200
        data = response.json()
        assert "transaction_id" in data

    # Verify second attempt fails
    response2 = client.post(f"/quotes/{quote.id}/payments")
    assert response2.status_code == 409
    assert "already has a payment transaction" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_updates_statuses(client, test_db_session):
    # Create quote and transaction
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=100.0,
        status=QuoteStatus.accepted,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    transaction = Transaction(
        quote_id=quote.id,
        provider=PaymentProvider.stripe,
        provider_id="pi_mock",
        amount_usd=100.0,
        status=TransactionStatus.pending,
    )
    test_db_session.add(transaction)
    test_db_session.commit()

    # Simulate webhook payload
    webhook_payload = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_mock", "status": "succeeded"}},
    }

    # Mock Stripe webhook verification
    mock_event = MagicMock()
    mock_event.type = "payment_intent.succeeded"
    mock_event.data.object.id = "pi_mock"
    mock_event.data.object.status = "succeeded"

    # Call webhook endpoint
    with (
        patch("api.webhooks.stripe") as mock_stripe,
        patch("api.webhooks.webhook_secret", "whsec_test_dummy"),
    ):
        mock_stripe.Webhook.construct_event.return_value = mock_event
        mock_stripe.error.SignatureVerificationError = (
            stripe.error.SignatureVerificationError
        )
        response = client.post(
            "/api/webhook/stripe",
            json=webhook_payload,
            headers={"stripe-signature": "mock_sig"},
        )
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.content}")

    assert response.status_code == 200

    # Verify status updates
    test_db_session.refresh(transaction)
    test_db_session.refresh(quote)
    assert transaction.status == TransactionStatus.succeeded
    assert quote.status == QuoteStatus.paid


@pytest.mark.asyncio
async def test_payment_failed_webhook(client, test_db_session):
    # Create quote and transaction
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=1,
        price=100.0,
        status=QuoteStatus.accepted,
    )
    test_db_session.add(quote)
    test_db_session.commit()

    transaction = Transaction(
        quote_id=quote.id,
        provider=PaymentProvider.stripe,
        provider_id="pi_mock_failed",
        amount_usd=100.0,
        status=TransactionStatus.pending,
    )
    test_db_session.add(transaction)
    test_db_session.commit()

    # Simulate webhook payload for payment_intent.payment_failed
    webhook_payload = {
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": "pi_mock_failed", "status": "failed"}},
    }

    # Mock Stripe webhook verification
    mock_event = MagicMock()
    mock_event.type = "payment_intent.payment_failed"
    mock_event.data.object.id = "pi_mock_failed"
    mock_event.data.object.status = "failed"

    with (
        patch("api.webhooks.stripe") as mock_stripe,
        patch("api.webhooks.webhook_secret", "whsec_test_dummy"),
    ):
        mock_stripe.Webhook.construct_event.return_value = mock_event
        mock_stripe.error.SignatureVerificationError = (
            stripe.error.SignatureVerificationError
        )
        response = client.post(
            "/api/webhook/stripe",
            json=webhook_payload,
            headers={"stripe-signature": "mock_sig"},
        )

    assert response.status_code == 200

    # Refresh from DB
    test_db_session.refresh(transaction)
    test_db_session.refresh(quote)
    assert transaction.status == TransactionStatus.failed
    assert quote.status == QuoteStatus.rejected
