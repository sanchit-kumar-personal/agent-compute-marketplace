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

    async def run(self, db: Session, quote_id: int) -> Quote:
        """Run the quote negotiation finite-state machine.

        Args:
            db: Database session
            quote_id: ID of the quote to negotiate

        Returns:
            Quote: Updated quote with negotiated price

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
            # Generate price through seller agent
            price = await self.seller.generate_quote(quote.__dict__)

            # Update quote
            quote.price = price
            quote.status = QuoteStatus.priced

            # Update negotiation log
            try:
                log = json.loads(quote.negotiation_log)
                if not isinstance(log, list):
                    log = []
            except json.JSONDecodeError:
                log = []

            # Add negotiation entry
            log.append(
                {
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    "role": "seller",
                    "price": price,
                    "action": "price_quote",
                }
            )
            quote.negotiation_log = log

            logger.info(f"Successfully negotiated quote {quote_id} price={price}")

            db.add(quote)
            return quote

        except Exception as e:
            logger.error(f"Failed to negotiate quote {quote_id}: {str(e)}")
            raise RuntimeError(f"Negotiation failed: {str(e)}")


def start_negotiation() -> SimpleNamespace:
    """Initialize a new negotiation session."""
    return SimpleNamespace(state="initialized")
