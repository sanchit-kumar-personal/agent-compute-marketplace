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
from negotiation.engine import NegotiationEngine
from agents.buyer import BuyerAgent
from agents.seller import SellerAgent


@pytest.fixture
def negotiation_engine():
    """Create a test instance of NegotiationEngine."""
    return NegotiationEngine()


@pytest.fixture
def buyer_agent():
    """Create a test instance of BuyerAgent."""
    return BuyerAgent()


@pytest.fixture
def seller_agent():
    """Create a test instance of SellerAgent."""
    return SellerAgent()


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
        "/api/quote-request",
        json={"buyer_id": "alice", "resource_type": "GPU", "duration_hours": 4},
    )
    assert resp.status_code == 201
    quote_id = resp.json()["quote_id"]

    # Negotiate
    nego = client.post(f"/api/quote/{quote_id}/negotiate")
    assert nego.status_code == 200
    data = nego.json()
    assert data["status"] == "priced"
    assert data["price"] == 8.0  # GPU base price (2.0) * 4 hours

    # Verify negotiation log
    log = data["negotiation_log"]  # Now directly a list
    assert len(log) == 1
    assert log[0]["role"] == "seller"

    # Try negotiating again - should fail with 409
    nego2 = client.post(f"/api/quote/{quote_id}/negotiate")
    assert nego2.status_code == 409
    assert "not in pending status" in nego2.json()["detail"]
