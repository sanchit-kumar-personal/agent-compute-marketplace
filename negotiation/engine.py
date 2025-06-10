"""
Negotiation Engine Module

This module implements the core negotiation logic using GPT-powered agents.
It manages the state machine for the negotiation process and uses LangChain/AutoGen
to generate dynamic counter-offers and acceptance logic. Key responsibilities:
- Orchestrating buyer-seller interactions
- Managing negotiation state transitions
- Applying negotiation strategies
- Generating context-aware responses
"""

import json
import datetime
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from db.models import Quote, QuoteStatus
from agents.seller import SellerAgent
from agents.buyer import BuyerAgent
import logging

logger = logging.getLogger(__name__)


@dataclass
class NegotiationState:
    """Represents the state of a negotiation."""

    state: str
    terms: Dict[str, Any]


class NegotiationEngine:
    """Core engine that manages the negotiation process between agents."""

    def __init__(self, seller: Optional[SellerAgent] = None):
        """Initialize the negotiation engine with default parameters."""
        self.state = "initialized"
        self.seller = seller or SellerAgent()

    async def start_negotiation(
        self, initial_terms: Dict[str, Any]
    ) -> NegotiationState:
        """Begin a new negotiation session with initial terms."""
        if not initial_terms:
            raise ValueError("Initial terms cannot be empty")
        return NegotiationState(state="initialized", terms=initial_terms)

    async def process_offer(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        """Process an offer and determine the next action."""
        if not offer or "price" not in offer:
            raise ValueError("Invalid offer format")
        return {"status": "processed", "offer": offer}

    async def generate_counter_offer(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a context-aware counter-offer using GPT."""
        if not context:
            raise ValueError("Context required for counter-offer")
        return {"status": "counter_offer_generated", "context": context}

    async def finalize_negotiation(self) -> Dict[str, str]:
        """Complete the negotiation and prepare for settlement."""
        return {"status": "finalized", "state": "completed"}

    async def run_loop(self, db: Session, quote_id: int, max_turns: int = 4) -> Quote:
        """Run multi-turn quote negotiation between buyer and seller.

        Args:
            db: Database session
            quote_id: ID of the quote to negotiate
            max_turns: Maximum number of negotiation turns before rejecting

        Returns:
            Quote: Updated quote with final negotiated price and status

        Raises:
            ValueError: If quote not found or not in pending status
            RuntimeError: If negotiation fails
        """
        quote: Quote | None = db.get(Quote, quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        if quote.status != QuoteStatus.pending:
            raise ValueError(f"Quote {quote_id} is not in pending status")

        try:
            # Initialize negotiation log
            try:
                log = json.loads(quote.negotiation_log)
                if not isinstance(log, list):
                    log = []
            except json.JSONDecodeError:
                log = []

            # Initial seller quote
            price = await self.seller.generate_quote(quote.__dict__)
            log.append(
                {
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    "role": "seller",
                    "price": price,
                    "action": "price_quote",
                }
            )
            quote.price = price
            quote.status = QuoteStatus.priced
            quote.negotiation_log = log

            db.add(quote)
            return quote

        except Exception as e:
            logger.error(f"Failed to negotiate quote {quote_id}: {str(e)}")
            raise RuntimeError(f"Negotiation failed: {str(e)}")

    async def negotiate(self, db: Session, quote_id: int, max_turns: int = 4) -> Quote:
        """Run multi-turn quote negotiation between buyer and seller.

        Args:
            db: Database session
            quote_id: ID of the quote to negotiate
            max_turns: Maximum number of negotiation turns before rejecting

        Returns:
            Quote: Updated quote with final negotiated price and status

        Raises:
            ValueError: If quote not found or not in priced status
            RuntimeError: If negotiation fails
        """
        quote: Quote | None = db.get(Quote, quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        if quote.status != QuoteStatus.priced:
            raise ValueError(f"Quote {quote_id} is not in priced status")

        try:
            # Initialize agents
            buyer = BuyerAgent(max_wtp=quote.buyer_max_price)

            # Initialize negotiation log
            try:
                log = json.loads(quote.negotiation_log)
                if not isinstance(log, list):
                    log = []
            except json.JSONDecodeError:
                log = []

            # Negotiation loop
            turns = 0
            price = quote.price
            while turns < max_turns:
                # Get buyer response
                buyer_response = await buyer.respond({"price": price})

                # Log buyer response
                log.append(
                    {
                        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                        "role": "buyer",
                        "response": buyer_response,
                        "action": (
                            "counter_offer" if buyer_response != "accept" else "accept"
                        ),
                    }
                )

                # Check if buyer accepts
                if buyer_response == "accept":
                    quote.status = QuoteStatus.accepted
                    break

                # Get seller counter-offer to buyer's price
                try:
                    counter_price = float(buyer_response)
                    price = await self.seller.generate_quote(
                        {**quote.__dict__, "counter_price": counter_price}
                    )

                    # Log seller response
                    log.append(
                        {
                            "timestamp": datetime.datetime.now(
                                datetime.UTC
                            ).isoformat(),
                            "role": "seller",
                            "price": price,
                            "action": "counter_offer",
                        }
                    )

                    quote.price = price
                    quote.status = QuoteStatus.countered

                except ValueError:
                    logger.error(f"Invalid buyer response: {buyer_response}")
                    quote.status = QuoteStatus.rejected
                    break

                turns += 1

            # If max turns reached without acceptance, mark as rejected
            if turns >= max_turns and quote.status != QuoteStatus.accepted:
                quote.status = QuoteStatus.rejected

            # Update negotiation log
            quote.negotiation_log = log

            logger.info(
                f"Completed negotiation for quote {quote_id} "
                f"status={quote.status} price={quote.price}"
            )

            db.add(quote)
            return quote

        except Exception as e:
            logger.error(f"Failed to negotiate quote {quote_id}: {str(e)}")
            raise RuntimeError(f"Negotiation failed: {str(e)}")


def start_negotiation() -> SimpleNamespace:
    """Initialize a new negotiation session."""
    return SimpleNamespace(state="initialized")
