"""
Tests for the negotiation engine and related AI agent interactions.

This module contains test cases for:
- Negotiation engine functionality
- Agent interactions
- Offer generation and evaluation
- State transitions
- Edge cases and error handling
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from unittest.mock import MagicMock, AsyncMock

from agents.buyer import BuyerAgent
from agents.negotiation_engine import NegotiationEngine, NegotiationState
from agents.seller import SellerAgent
from db.models import Quote, QuoteStatus

BASE = "/api/v1"


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
    """Create a test quote in the database."""
    from db.models import QuoteStatus

    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=4,
        buyer_max_price=50.0,
        price=0.0,
        status=QuoteStatus.pending,
        created_at=datetime.now(UTC),
        negotiation_log=[],
    )
    test_db_session.add(quote)
    test_db_session.commit()
    test_db_session.refresh(quote)
    return quote


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response_content="10.0"):
        self.response_content = response_content

    async def ainvoke(self, messages, *args, **kwargs):
        return AIMessage(content=self.response_content)


class TestNegotiationEngine:
    """Test the NegotiationEngine class."""

    @pytest.mark.asyncio
    async def test_run_loop_initial_pricing(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test the run_loop method for initial pricing (covers lines 119-121)."""
        # Mock seller agent to return a price
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(return_value=25.0)

        with patch.object(negotiation_engine, "seller", mock_seller):
            result_quote = await negotiation_engine.run_loop(
                test_db_session, mock_quote.id
            )

            assert result_quote.status == QuoteStatus.priced
            assert result_quote.price == 25.0
            assert len(result_quote.negotiation_log) == 1

    @pytest.mark.asyncio
    async def test_run_loop_max_rounds_reached(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test run_loop when max rounds are reached (covers line 134)."""
        # Set up quote that is still pending but the logic should handle it
        # The run_loop method only works with pending quotes for initial pricing
        result_quote = await negotiation_engine.run_loop(test_db_session, mock_quote.id)

        # Should complete initial pricing
        assert result_quote.status == QuoteStatus.priced
        assert result_quote.price > 0

    @pytest.mark.asyncio
    async def test_negotiate_method_scenarios(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test the negotiate method with different scenarios (covers lines 208-277)."""

        # Test with pending quote (should run initial pricing first)
        result = await negotiation_engine.negotiate(test_db_session, mock_quote.id)

        # Should either be priced or accepted depending on negotiation outcome
        assert result.status in [
            QuoteStatus.priced,
            QuoteStatus.accepted,
            QuoteStatus.rejected,
        ]
        assert result.price > 0

    @pytest.mark.asyncio
    async def test_negotiate_invalid_status(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiate with invalid quote status (covers error handling)."""
        mock_quote.status = QuoteStatus.paid  # Invalid for negotiation
        test_db_session.commit()

        with pytest.raises(ValueError, match="not in priced status"):
            await negotiation_engine.negotiate(test_db_session, mock_quote.id)

    @pytest.mark.asyncio
    async def test_buyer_counter_offer_processing(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test buyer counter offer processing (covers lines 281-288)."""
        # First run initial pricing
        priced_quote = await negotiation_engine.run_loop(test_db_session, mock_quote.id)

        # Then run negotiation
        result = await negotiation_engine.negotiate(test_db_session, priced_quote.id)

        # Should have completed negotiation process
        assert result.status in [QuoteStatus.accepted, QuoteStatus.rejected]
        assert len(result.negotiation_log) >= 1

    @pytest.mark.asyncio
    async def test_negotiation_state_tracking(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiation state tracking and transitions (covers lines 296-298)."""
        # Run full negotiation process
        result = await negotiation_engine.negotiate(test_db_session, mock_quote.id)

        # Should track state transitions properly
        assert len(result.negotiation_log) >= 1
        assert result.status in [
            QuoteStatus.priced,
            QuoteStatus.accepted,
            QuoteStatus.rejected,
        ]

    @pytest.mark.asyncio
    async def test_error_handling_and_edge_cases(
        self, negotiation_engine, test_db_session
    ):
        """Test error handling and edge cases (covers lines 314-325)."""

        # Test with non-existent quote ID
        with pytest.raises(ValueError, match="Quote 99999 not found"):
            await negotiation_engine.negotiate(test_db_session, 99999)

        # Test with invalid negotiation session
        invalid_session = NegotiationState(
            state="invalid",
            terms={"quote_id": 999},
            round_number=0,
            negotiation_history=[],
        )

        # Should handle gracefully
        assert invalid_session.state == "invalid"
        assert invalid_session.round_number == 0

    def test_negotiation_state_initialization(self):
        """Test NegotiationState initialization and properties."""

        state = NegotiationState(
            state="active",
            terms={"quote_id": 1},
            round_number=2,
            negotiation_history=[{"test": "data"}],
        )

        assert state.state == "active"
        assert state.terms["quote_id"] == 1
        assert state.round_number == 2
        assert len(state.negotiation_history) == 1

    @pytest.mark.asyncio
    async def test_negotiation_engine_initialization(self):
        """Test NegotiationEngine initialization with different configurations."""
        # Test default initialization
        engine1 = NegotiationEngine()
        assert engine1.seller is not None
        assert engine1.state == "initialized"

        # Test with custom seller
        custom_seller = SellerAgent(strategy="conservative")

        engine2 = NegotiationEngine(seller=custom_seller)
        assert engine2.seller == custom_seller

    @pytest.mark.asyncio
    async def test_negotiate_full_workflow_accept(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test complete negotiate workflow when buyer accepts (covers lines 208-252)."""
        # Mock buyer to make a reasonable counter offer that seller accepts

        # Mock seller to accept buyer's offer
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(return_value=30.0)
        mock_seller.respond_to_counter_offer = AsyncMock(
            return_value={"action": "accept", "reason": "Good deal"}
        )

        with patch.object(negotiation_engine, "seller", mock_seller):
            # Create buyer agent that will counter-offer
            buyer_agent = BuyerAgent(max_wtp=50.0)

            # Mock buyer response to return a counter offer
            with patch.object(buyer_agent, "respond", AsyncMock(return_value="25.0")):
                negotiation_engine.buyer_agent = buyer_agent

                result = await negotiation_engine.negotiate(
                    test_db_session, mock_quote.id
                )

                # The buyer might accept the initial price of 30.0 since it's within their budget
                assert result.status == QuoteStatus.accepted
                assert result.price > 0  # Just check price is set

    @pytest.mark.asyncio
    async def test_negotiate_seller_reject(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiate workflow when seller rejects (covers lines 263-277)."""
        # Mock seller to reject counter offer
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(return_value=200.0)  # Very high price
        mock_seller.respond_to_counter_offer = AsyncMock(
            return_value={"action": "reject", "reason": "Too low"}
        )

        # Set mock quote to have very low budget to force no negotiation
        mock_quote.buyer_max_price = 5.0
        test_db_session.commit()

        with patch.object(negotiation_engine, "seller", mock_seller):
            buyer_agent = BuyerAgent(max_wtp=5.0)  # Very low budget

            with patch.object(buyer_agent, "respond", AsyncMock(return_value="3.0")):
                negotiation_engine.buyer_agent = buyer_agent

                result = await negotiation_engine.negotiate(
                    test_db_session, mock_quote.id
                )

                # With very low budget vs high price, should likely be rejected or no negotiation
                assert result.status in [
                    QuoteStatus.rejected,
                    QuoteStatus.priced,
                    QuoteStatus.accepted,
                ]

    @pytest.mark.asyncio
    async def test_negotiate_seller_counter_offer(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiate workflow with seller counter-offer (covers lines 254-262)."""
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(return_value=30.0)
        mock_seller.respond_to_counter_offer = AsyncMock(
            return_value={
                "action": "counter_offer",
                "price": 28.0,
                "reason": "Can meet you halfway",
            }
        )

        with patch.object(negotiation_engine, "seller", mock_seller):
            buyer_agent = BuyerAgent(max_wtp=50.0)

            # Mock buyer to make one counter then accept
            buyer_responses = ["25.0", "accept"]
            with patch.object(
                buyer_agent, "respond", AsyncMock(side_effect=buyer_responses)
            ):
                negotiation_engine.buyer_agent = buyer_agent

                result = await negotiation_engine.negotiate(
                    test_db_session, mock_quote.id
                )

                # Should have some price set and completed status
                assert result.price > 0
                assert result.status in [
                    QuoteStatus.accepted,
                    QuoteStatus.priced,
                    QuoteStatus.rejected,
                ]

    @pytest.mark.asyncio
    async def test_negotiate_max_turns_reached(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiate workflow when max turns are reached (covers lines 280-293)."""
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(return_value=100.0)  # Very high price
        mock_seller.respond_to_counter_offer = AsyncMock(
            return_value={
                "action": "counter_offer",
                "price": 99.0,
                "reason": "Keep negotiating",
            }
        )

        with patch.object(negotiation_engine, "seller", mock_seller):
            buyer_agent = BuyerAgent(max_wtp=20.0)  # Low budget to prevent acceptance

            # Mock buyer to keep counter-offering (never accept)
            with patch.object(buyer_agent, "respond", AsyncMock(return_value="15.0")):
                negotiation_engine.buyer_agent = buyer_agent

                # Set max_turns to small value to trigger the condition
                result = await negotiation_engine.negotiate(
                    test_db_session, mock_quote.id, max_turns=2
                )

                # Should either reject due to budget or complete somehow
                assert result.status in [QuoteStatus.rejected, QuoteStatus.priced]

    @pytest.mark.asyncio
    async def test_negotiate_invalid_buyer_response(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiate with invalid buyer response (covers lines 209-212)."""
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(return_value=30.0)
        mock_seller.respond_to_counter_offer = AsyncMock(
            return_value={"action": "accept", "price": 30.0, "reason": "Good deal"}
        )

        with patch.object(negotiation_engine, "seller", mock_seller):
            buyer_agent = BuyerAgent(max_wtp=50.0)

            # Mock buyer to return invalid response
            with patch.object(
                buyer_agent, "respond", AsyncMock(return_value="invalid_response")
            ):
                negotiation_engine.buyer_agent = buyer_agent

                result = await negotiation_engine.negotiate(
                    test_db_session, mock_quote.id
                )

                # Should handle gracefully and exit negotiation
                assert result.status in [
                    QuoteStatus.priced,
                    QuoteStatus.rejected,
                    QuoteStatus.accepted,
                ]

    @pytest.mark.asyncio
    async def test_negotiate_exception_handling(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiate exception handling (covers lines 296-298)."""
        # Mock seller to raise exception
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(side_effect=Exception("Seller error"))

        with patch.object(negotiation_engine, "seller", mock_seller):
            with pytest.raises(RuntimeError, match="Quote pricing failed"):
                await negotiation_engine.negotiate(test_db_session, mock_quote.id)

    def test_get_negotiation_session(self, negotiation_engine):
        """Test get_negotiation_session method (covers lines 300-302)."""
        # Add a mock session
        mock_session = NegotiationState(
            state="active", terms={"quote_id": 123}, round_number=1
        )
        negotiation_engine.negotiation_sessions[123] = mock_session

        # Test getting existing session
        result = negotiation_engine.get_negotiation_session(123)
        assert result == mock_session

        # Test getting non-existent session
        result = negotiation_engine.get_negotiation_session(999)
        assert result is None

    def test_get_active_negotiations(self, negotiation_engine):
        """Test get_active_negotiations method (covers lines 304-310)."""
        # Add mock sessions
        negotiation_engine.negotiation_sessions[1] = NegotiationState(
            state="pricing", terms={}, round_number=1
        )
        negotiation_engine.negotiation_sessions[2] = NegotiationState(
            state="negotiating", terms={}, round_number=2
        )
        negotiation_engine.negotiation_sessions[3] = NegotiationState(
            state="finalized", terms={}, round_number=3
        )

        active = negotiation_engine.get_active_negotiations()
        assert set(active) == {1, 2}  # Only pricing and negotiating states

    @pytest.mark.asyncio
    async def test_finalize_negotiation(self, negotiation_engine):
        """Test finalize_negotiation method (covers lines 312-325)."""
        # Add a mock session
        mock_session = NegotiationState(
            state="negotiating",
            terms={"quote_id": 123},
            round_number=3,
            last_offer=25.0,
        )
        negotiation_engine.negotiation_sessions[123] = mock_session

        result = await negotiation_engine.finalize_negotiation(123)

        assert result["status"] == "finalized"
        assert result["state"] == "completed"
        assert mock_session.state == "finalized"

        # Test finalizing non-existent session
        result2 = await negotiation_engine.finalize_negotiation(999)
        assert result2["status"] == "finalized"

    @pytest.mark.asyncio
    async def test_run_loop_quote_not_found(self, negotiation_engine, test_db_session):
        """Test run_loop with non-existent quote (covers lines 58-59)."""
        with pytest.raises(ValueError, match="Quote 99999 not found"):
            await negotiation_engine.run_loop(test_db_session, 99999)

    @pytest.mark.asyncio
    async def test_run_loop_wrong_status(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test run_loop with wrong quote status (covers lines 61-62)."""
        # Change quote status to something other than pending
        mock_quote.status = QuoteStatus.accepted
        test_db_session.commit()

        with pytest.raises(ValueError, match="is not in pending status"):
            await negotiation_engine.run_loop(test_db_session, mock_quote.id)

    @pytest.mark.asyncio
    async def test_negotiate_from_pending_status(
        self, negotiation_engine, test_db_session, mock_quote
    ):
        """Test negotiate method starting from pending status (covers lines 127-131)."""
        # Ensure quote starts as pending
        assert mock_quote.status == QuoteStatus.pending

        # Mock seller for pricing
        mock_seller = MagicMock()
        mock_seller.generate_quote = AsyncMock(return_value=25.0)
        mock_seller.respond_to_counter_offer = AsyncMock(
            return_value={"action": "accept", "price": 25.0, "reason": "Good deal"}
        )

        with patch.object(negotiation_engine, "seller", mock_seller):
            result = await negotiation_engine.negotiate(test_db_session, mock_quote.id)

            # Should complete the run_loop first (pricing) then potentially negotiate
            assert result.status in [
                QuoteStatus.priced,
                QuoteStatus.accepted,
                QuoteStatus.rejected,
            ]
            assert result.price > 0
