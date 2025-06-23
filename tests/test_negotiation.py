"""
Negotiation Tests Module

This module contains test cases for:
- Negotiation engine functionality
- Agent interactions
- Offer generation and evaluation
- State transitions
- Edge cases and error handling
"""

import pytest
from unittest.mock import patch
from negotiation.engine import NegotiationEngine
from agents.buyer import BuyerAgent
from agents.seller import SellerAgent
from db.models import Quote, QuoteStatus
from datetime import datetime, UTC
from langchain_core.messages import AIMessage


@pytest.fixture
def negotiation_engine():
    """Create a test instance of NegotiationEngine."""
    return NegotiationEngine()


@pytest.fixture
def buyer_agent():
    """Create a test instance of BuyerAgent."""
    return BuyerAgent(max_wtp=5.0)


@pytest.fixture
def seller_agent():
    """Create a test instance of SellerAgent."""
    return SellerAgent()


@pytest.fixture
def mock_quote(test_db_session):
    """Create a test quote in pending status."""
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=4,
        status=QuoteStatus.pending,
        buyer_max_price=5.0,
        created_at=datetime.now(UTC),
        negotiation_log="[]",
    )
    test_db_session.add(quote)
    test_db_session.commit()
    test_db_session.refresh(quote)
    return quote


class MockLLM:
    """Mock LLM for deterministic test responses."""

    def __init__(self, responses):
        self.responses = responses
        self.index = 0

    async def ainvoke(self, messages, *args, **kwargs):
        response = self.responses[self.index]
        self.index += 1
        return AIMessage(content=response)

    async def __call__(self, messages, *args, **kwargs):
        response = self.responses[self.index]
        self.index += 1
        return AIMessage(content=response)


@pytest.mark.asyncio
async def test_multi_turn_negotiation_accepted(mock_quote, test_db_session):
    """Test successful multi-turn negotiation ending in acceptance."""

    # Mock sequence: seller 5.0 -> buyer 4.0 -> seller 4.5 -> buyer accept
    seller_responses = ["5.0", "4.5"]
    buyer_responses = ["4.0", "accept"]

    with patch("agents.seller.get_llm") as mock_seller_llm, patch(
        "agents.buyer.get_llm"
    ) as mock_buyer_llm:

        mock_seller_llm.return_value = MockLLM(seller_responses)
        mock_buyer_llm.return_value = MockLLM(buyer_responses)

        seller = SellerAgent()
        engine = NegotiationEngine(seller)

        # First get initial quote
        quote = await engine.run_loop(test_db_session, mock_quote.id)
        assert quote.status == QuoteStatus.priced

        # Then run negotiation
        quote = await engine.negotiate(test_db_session, mock_quote.id)

        # Verify final state
        assert quote.status == QuoteStatus.accepted
        assert quote.price == 4.5

        # Verify negotiation log
        log = quote.negotiation_log  # Already a list, no need for json.loads()
        assert len(log) == 4

        # Check sequence
        assert log[0]["role"] == "seller" and float(log[0]["price"]) == 5.0
        assert log[1]["role"] == "buyer" and log[1]["response"] == "4.0"
        assert log[2]["role"] == "seller" and float(log[2]["price"]) == 4.5
        assert log[3]["role"] == "buyer" and log[3]["response"] == "accept"


@pytest.mark.asyncio
async def test_auto_negotiate_endpoint(client, mock_quote, test_db_session):
    """Test the auto-negotiation endpoint behavior."""

    # First call should create payment intent and transaction
    with patch("stripe.PaymentIntent.create") as mock_create:
        mock_create.return_value = type(
            "PaymentIntent",
            (),
            {
                "id": "pi_mock",
                "client_secret": "secret",
                "status": "requires_payment_method",  # Initial Stripe status
            },
        )()
        resp1 = client.post(f"/quotes/{mock_quote.id}/negotiate/auto")
        assert resp1.status_code == 200
        data = resp1.json()
        assert data["status"] == "accepted"  # Quote should be in accepted state
        assert "transactions" in data

        # Verify transaction starts as pending
        transactions = data["transactions"]
        assert len(transactions) == 1
        tx = transactions[0]
        assert tx["provider"] == "stripe"
        assert tx["status"] == "pending"  # Transaction starts as pending
        assert tx["provider_id"] == "pi_mock"

    # Simulate webhook for successful payment
    webhook_payload = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_mock", "status": "succeeded"}},
    }

    # Mock Stripe webhook verification
    mock_event = type(
        "Event",
        (),
        {
            "type": "payment_intent.succeeded",
            "data": type(
                "Data",
                (),
                {
                    "object": type(
                        "Object", (), {"id": "pi_mock", "status": "succeeded"}
                    )
                },
            ),
        },
    )()

    # Use the test client to call the webhook endpoint
    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        webhook_response = client.post(
            "/api/webhook/stripe",
            json=webhook_payload,
            headers={"stripe-signature": "test_sig"},
        )
        assert webhook_response.status_code == 200
        assert webhook_response.json() == {"status": "success"}

    # Verify final states after webhook
    test_db_session.refresh(mock_quote)
    assert mock_quote.status == QuoteStatus.paid
    assert mock_quote.price == 100.0  # Mock price

    # Second call should fail since quote is no longer pending
    resp2 = client.post(f"/quotes/{mock_quote.id}/negotiate/auto")
    assert resp2.status_code == 409
    assert "not in pending status" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_start_negotiation(negotiation_engine):
    """Test starting a new negotiation session."""
    initial_terms = {
        "resource_type": "GPU",
        "hours_needed": 4,
        "max_price_per_hour": 10.0,
    }
    result = await negotiation_engine.start_negotiation(initial_terms)
    assert result.state == "initialized"


@pytest.mark.asyncio
async def test_offer_generation(buyer_agent):
    """Test buyer agent's offer generation."""
    offer = await buyer_agent.make_offer()
    assert isinstance(offer, dict)
    assert "price" in offer


@pytest.mark.unit
def test_negotiate_quote_flow(client):
    """Test the full quote negotiation flow from creation to pricing."""
    # Create quote first
    resp = client.post(
        "/quotes/request",
        json={"buyer_id": "alice", "resource_type": "GPU", "duration_hours": 4},
    )
    assert resp.status_code == 201
    quote_id = resp.json()["quote_id"]

    # Negotiate
    nego = client.post(f"/quotes/{quote_id}/negotiate")
    assert nego.status_code == 200
    data = nego.json()
    assert data["status"] == "priced"
    assert data["price"] == 8.0  # GPU base price (2.0) * 4 hours

    # Verify negotiation log
    log = data["negotiation_log"]  # Now directly a list
    assert len(log) == 1
    assert log[0]["role"] == "seller"

    # Try negotiating again - should fail with 409
    nego2 = client.post(f"/quotes/{quote_id}/negotiate")
    assert nego2.status_code == 409
    assert "not in pending status" in nego2.json()["detail"]
