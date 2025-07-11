import pytest

from db.models import PaymentProvider, QuoteStatus, TransactionStatus


@pytest.fixture(autouse=True)
def mock_paypal(monkeypatch):
    from payments import paypal_service

    def mock_create_and_capture(self, amt, qid):
        # Return success by default
        return {"capture_id": "CAPTURE_MOCK", "status": "COMPLETED"}

    monkeypatch.setattr(
        paypal_service.PayPalService, "create_and_capture", mock_create_and_capture
    )
    yield


def test_paypal_success_flow(client):
    """Test successful PayPal payment flow."""
    # Create quote
    r = client.post(
        "/quotes/request",
        json={
            "buyer_id": "pp_user",
            "resource_type": "GPU",
            "duration_hours": 1,
            "buyer_max_price": 10.0,
        },
    )
    assert r.status_code == 201
    quote_id = r.json()["quote_id"]

    # Negotiate auto with PayPal - should succeed
    res = client.post(f"/quotes/{quote_id}/negotiate/auto?provider=paypal")
    assert res.status_code == 200
    quote = res.json()
    assert quote["status"] == QuoteStatus.paid.value

    # Verify transactions
    transactions = quote.get("transactions", [])
    assert len(transactions) > 0
    tx = transactions[0]
    assert tx["provider"] == PaymentProvider.paypal.value
    assert tx["status"] == TransactionStatus.succeeded.value


def test_paypal_failure_flow(client, monkeypatch):
    """Test failed PayPal payment flow."""

    # Mock PayPal to return failed status
    def mock_failed_capture(self, amt, qid):
        return {"capture_id": "CAPTURE_MOCK", "status": "FAILED"}

    monkeypatch.setattr(
        "payments.paypal_service.PayPalService.create_and_capture", mock_failed_capture
    )

    # Create quote
    r = client.post(
        "/quotes/request",
        json={
            "buyer_id": "pp_user",
            "resource_type": "GPU",
            "duration_hours": 1,
            "buyer_max_price": 10.0,
        },
    )
    assert r.status_code == 201
    quote_id = r.json()["quote_id"]

    # Negotiate auto with PayPal - should fail with 402
    res = client.post(f"/quotes/{quote_id}/negotiate/auto?provider=paypal")
    assert res.status_code == 402
    assert "paypal capture declined" in res.json()["detail"]

    # Verify quote is in rejected state
    quote = client.get(f"/quotes/{quote_id}")
    assert quote.status_code == 200
    assert quote.json()["status"] == QuoteStatus.rejected.value

    # Verify transaction was created and marked as failed
    transactions = quote.json()["transactions"]
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx["provider"] == PaymentProvider.paypal.value
    assert tx["status"] == TransactionStatus.failed.value
    assert tx["provider_id"] == "CAPTURE_MOCK"


def test_paypal_declined(client, monkeypatch):
    """Test PayPal declined payment flow."""
    from db.models import Quote, QuoteStatus
    from payments import paypal_service

    # Mock PayPal to return declined status
    monkeypatch.setattr(
        paypal_service.PayPalService,
        "create_and_capture",
        lambda self, amt, qid: {"capture_id": "CAP-FAIL", "status": "DECLINED"},
    )

    # Create quote request
    res = client.post(
        "/quotes/request",
        json={
            "buyer_id": "pp2",
            "resource_type": "GPU",
            "duration_hours": 1,
            "buyer_max_price": 10.0,
        },
    )
    assert res.status_code == 201
    qid = res.json()["quote_id"]

    # Get quote - should be in pending state
    quote = client.get(f"/quotes/{qid}")
    assert quote.status_code == 200
    assert quote.json()["status"] == QuoteStatus.pending.value

    # Mock the negotiation engine to set a price
    from negotiation.engine import NegotiationEngine

    def mock_run_loop(self, db, quote_id):
        quote = db.get(Quote, quote_id)
        quote.price = 100.0
        quote.status = QuoteStatus.priced
        return quote

    monkeypatch.setattr(NegotiationEngine, "run_loop", mock_run_loop)

    # Attempt payment with PayPal - should fail with 402
    resp = client.post(f"/quotes/{qid}/negotiate/auto?provider=paypal")
    assert resp.status_code == 402
    assert "paypal capture declined" in resp.json()["detail"]

    # Verify quote is in rejected state
    quote = client.get(f"/quotes/{qid}")
    assert quote.status_code == 200
    assert quote.json()["status"] == QuoteStatus.rejected.value

    # Verify transaction was created and marked as failed
    transactions = quote.json()["transactions"]
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx["provider"] == PaymentProvider.paypal.value
    assert tx["status"] == TransactionStatus.failed.value
    assert tx["provider_id"] == "CAP-FAIL"
