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


@pytest.mark.asyncio
async def test_counter_offer(seller_agent):
    """Test seller agent's counter-offer generation."""
    initial_offer = {"price": 8.0, "hours": 4}
    counter_offer = await seller_agent.make_counter_offer()
    assert isinstance(counter_offer, dict)
    assert counter_offer["price"] > initial_offer["price"]
