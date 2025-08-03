"""
Comprehensive PayPal payment tests for MVP architecture.
"""

import requests
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC, timedelta
from decimal import Decimal

from db.models import PaymentProvider, QuoteStatus, TransactionStatus
from payments.paypal_service import PayPalService

BASE = "/api/v1"


class MockResponse:
    """Custom mock response class to ensure proper status_code handling."""

    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code  # This is definitely an integer
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        pass


def test_paypal_service_initialization():
    """Test PayPal service initialization."""
    service = PayPalService()
    assert service.base is not None
    assert service.client is not None
    assert service.secret is not None


def test_paypal_map_status():
    """Test PayPal status mapping to internal TransactionStatus."""
    # Test completed status
    assert PayPalService.map_status("COMPLETED") == TransactionStatus.succeeded

    # Test other statuses default to failed
    assert PayPalService.map_status("FAILED") == TransactionStatus.failed
    assert PayPalService.map_status("DECLINED") == TransactionStatus.failed
    assert PayPalService.map_status("PENDING") == TransactionStatus.failed
    assert PayPalService.map_status("UNKNOWN") == TransactionStatus.failed


@patch("payments.paypal_service.requests.post")
def test_paypal_token_functionality(mock_post):
    """Test PayPal token retrieval and caching."""
    # Clear any existing cache
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    # Mock successful token response
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "test_access_token"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    service = PayPalService()

    # First call should make HTTP request
    token1 = service._token()
    assert token1 == "test_access_token"
    assert mock_post.call_count == 1

    # Second call should use cache (no additional HTTP request)
    token2 = service._token()
    assert token2 == "test_access_token"
    assert mock_post.call_count == 1  # Still only 1 call


@patch("payments.paypal_service.requests.post")
def test_paypal_token_caching_expiry(mock_post):
    """Test that PayPal token cache expires correctly."""
    # Clear any existing cache
    import payments.paypal_service

    # Set up expired cache
    expired_time = datetime.now(UTC) - timedelta(minutes=10)
    payments.paypal_service._TOKEN_CACHE = ("expired_token", expired_time)

    # Mock new token response
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "new_token"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    service = PayPalService()
    token = service._token()

    # Should get new token, not expired one
    assert token == "new_token"
    mock_post.assert_called_once()


@patch("payments.paypal_service.requests.post")
def test_paypal_invoicing_success_full_flow(mock_post):
    """Test successful PayPal invoicing flow (MVP implementation)."""
    service = PayPalService()

    # Clear token cache for consistent testing
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    # Use MockResponse objects with explicit integer status codes
    token_response = MockResponse(200, {"access_token": "test_token"})
    invoice_response = MockResponse(
        201, {"id": "INV-TEST-12345"}
    )  # This should come second
    send_response = MockResponse(202)
    payment_response = MockResponse(204)

    mock_post.side_effect = [
        token_response,
        invoice_response,
        send_response,
        payment_response,
    ]

    result = service.create_and_capture(50.0, 123)

    # Verify the full invoicing flow worked
    assert result["status"] == "COMPLETED"
    assert result["capture_id"] == "INV-TEST-12345"
    assert result["invoice_id"] == "INV-TEST-12345"
    assert result["amount"] == "50.00"
    assert result["currency"] == "USD"
    assert result["real_paypal_invoice"] is True
    assert "REAL PayPal invoice created, sent, and paid!" in result["demo_note"]

    # Verify all the API calls were made
    assert mock_post.call_count == 4  # token, create, send, payment


@patch("payments.paypal_service.requests.post")
def test_paypal_invoicing_href_response_format(mock_post):
    """Test PayPal invoicing with href response format."""
    service = PayPalService()

    # Clear token cache for consistent testing
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    token_response = MockResponse(200, {"access_token": "test_token"})
    invoice_response = MockResponse(
        201,
        {  # This should come second
            "href": "https://api.paypal.com/v2/invoicing/invoices/INV-HREF-789",
            "other_field": "value",
        },
    )
    send_response = MockResponse(202)
    payment_response = MockResponse(204)

    mock_post.side_effect = [
        token_response,
        invoice_response,
        send_response,
        payment_response,
    ]

    result = service.create_and_capture(75.0, 456)

    # Should extract ID from href and complete successfully
    assert result["status"] == "COMPLETED"
    assert result["invoice_id"] == "INV-HREF-789"
    assert result["capture_id"] == "INV-HREF-789"


@patch("payments.paypal_service.requests.post")
def test_paypal_invoicing_creation_failure(mock_post):
    """Test PayPal invoice creation failure."""
    service = PayPalService()

    # Clear token cache for consistent testing
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    token_response = MockResponse(200, {"access_token": "test_token"})
    invoice_response = MockResponse(
        400, text="Invalid invoice data"
    )  # This should come second

    mock_post.side_effect = [token_response, invoice_response]

    # Should fall back to demo mode instead of raising exception
    result = service.create_and_capture(50.0, 123)

    # Should get demo fallback
    assert result["status"] == "COMPLETED"
    assert result["demo_mode"] is True
    assert "demo_cap_123" in result["capture_id"]


@patch("payments.paypal_service.requests.post")
def test_paypal_invoicing_missing_id_fields(mock_post):
    """Test PayPal invoice response missing both id and href fields."""
    service = PayPalService()

    # Clear any existing token cache for this test
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    # The @tenacity.retry decorator will retry 3 times total
    # First call: token (cached for subsequent calls)
    # Then: 3 invoice calls (original + 2 retries) before giving up
    token_response = MockResponse(200, {"access_token": "test_token"})
    invoice_response = MockResponse(
        201, {"other_field": "value", "no_id_or_href": True}
    )

    # Provide: 1 token + 3 invoice calls (tenacity retries 3 times total)
    mock_post.side_effect = [
        token_response,  # Token call (gets cached)
        invoice_response,  # First invoice attempt
        invoice_response,  # Second invoice attempt (retry)
        invoice_response,  # Third invoice attempt (retry)
    ]

    # Should fall back to demo mode when ValueError is caught after retries
    result = service.create_and_capture(50.0, 123)

    # Should get demo fallback
    assert result["status"] == "COMPLETED"
    assert result["demo_mode"] is True
    assert "demo_cap_123" in result["capture_id"]


@patch("payments.paypal_service.requests.post")
def test_paypal_invoicing_send_failure_still_succeeds(mock_post):
    """Test PayPal invoice send failure still returns success (invoice was created)."""
    service = PayPalService()

    # Clear token cache for consistent testing
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    token_response = MockResponse(200, {"access_token": "test_token"})
    invoice_response = MockResponse(
        201, {"id": "INV-SEND-FAIL"}
    )  # This should come second
    send_response = MockResponse(500)  # Server error

    mock_post.side_effect = [token_response, invoice_response, send_response]

    result = service.create_and_capture(50.0, 123)

    # Should still return success since invoice was created
    assert result["status"] == "COMPLETED"
    assert result["invoice_id"] == "INV-SEND-FAIL"
    assert "invoice exists" in result["demo_note"]


@patch("payments.paypal_service.requests.post")
def test_paypal_invoicing_payment_recording_failure(mock_post):
    """Test PayPal payment recording failure still completes (demo behavior)."""
    service = PayPalService()

    # Clear token cache for consistent testing
    import payments.paypal_service

    payments.paypal_service._TOKEN_CACHE = None

    token_response = MockResponse(200, {"access_token": "test_token"})
    invoice_response = MockResponse(
        201, {"id": "INV-PAY-FAIL"}
    )  # This should come second
    send_response = MockResponse(202)
    payment_response = MockResponse(400)  # Bad request

    mock_post.side_effect = [
        token_response,
        invoice_response,
        send_response,
        payment_response,
    ]

    result = service.create_and_capture(50.0, 123)

    # Should still complete successfully with demo note
    assert result["status"] == "COMPLETED"
    assert "marked as paid for demo" in result["demo_note"]


@patch("payments.paypal_service.requests.post")
def test_paypal_invoicing_api_exception_fallback(mock_post):
    """Test PayPal API exception triggers demo fallback."""
    service = PayPalService()

    # Mock complete API failure - this will cause RequestException in the except block
    mock_post.side_effect = requests.RequestException(
        "PayPal API completely unavailable"
    )

    result = service.create_and_capture(100.0, 789)

    # Should fall back to demo mode
    assert result["status"] == "COMPLETED"
    assert result["demo_mode"] is True
    assert "demo_cap_789" in result["capture_id"]
    assert "Demo transaction due to PayPal API error" in result["demo_note"]


@patch("payments.paypal_service.PayPalService.create_and_capture")
def test_paypal_direct_payment_integration(
    mock_create_capture, client, test_db_session
):
    """Test direct PayPal payment creation via payments endpoint."""
    from db.models import Quote

    # Mock the PayPal service to return success
    mock_create_capture.return_value = {
        "capture_id": "INV-INTEGRATION-TEST",
        "status": "COMPLETED",
        "transaction_status": TransactionStatus.succeeded,
        "amount": "50.00",
        "currency": "USD",
        "invoice_id": "INV-INTEGRATION-TEST",
        "real_paypal_invoice": True,
        "demo_note": "Integration test invoice",
    }

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

    response = client.post(
        f"{BASE}/quotes/{quote.id}/payments?provider=paypal",
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["provider"] == "paypal"
    assert "capture_id" in data
    assert data["amount"] == 50.0

    # Verify transaction was created and quote updated (MVP behavior)
    test_db_session.refresh(quote)
    assert quote.status == QuoteStatus.paid

    from db.models import Transaction

    transaction = (
        test_db_session.query(Transaction).filter_by(quote_id=quote.id).first()
    )
    assert transaction is not None
    assert transaction.provider == PaymentProvider.paypal
    assert transaction.status == TransactionStatus.succeeded

    # Verify the service method was called
    mock_create_capture.assert_called_once_with(
        amount=Decimal("50.0"), quote_id=quote.id
    )
