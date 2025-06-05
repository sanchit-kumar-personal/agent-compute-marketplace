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

    async def start_negotiation(self, initial_terms: Dict[str, Any]):
        """Begin a new negotiation session with initial terms."""
        return NegotiationState(state="initialized", terms=initial_terms)

    async def process_offer(self, offer: Dict[str, Any]):
        """Process an offer and determine the next action."""
        pass

    async def generate_counter_offer(self, context: Dict[str, Any]):
        """Generate a context-aware counter-offer using GPT."""
        pass

    async def finalize_negotiation(self):
        """Complete the negotiation and prepare for settlement."""
        pass

    def run(self, db: Session, quote_id: int) -> Quote:
        """Run the quote negotiation finite-state machine.

        Only runs if Quote.status == pending:
        1. Calls SellerAgent.generate_quote → gets price
        2. Updates quote.price and quote.status = QuoteStatus.priced
        3. Appends a message object to negotiation_log
        """
        quote: Quote | None = db.get(Quote, quote_id)
        if not quote or quote.status != QuoteStatus.pending:
            raise ValueError("Quote not found or not pending")

        price = self.seller.generate_quote(quote.__dict__)
        quote.price = price
        quote.status = QuoteStatus.priced

        try:
            log = json.loads(quote.negotiation_log)
            if not isinstance(log, list):
                log = []
        except json.JSONDecodeError:
            log = []

        log.append(
            {
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "role": "seller",
                "price": price,
            }
        )
        quote.negotiation_log = log  # Will be automatically JSON encoded

        logger.info(f"Negotiated quote {quote_id} price={price}")

        db.add(quote)  # Let FastAPI handle the transaction
        return quote


def start_negotiation() -> SimpleNamespace:
    """Initialize a new negotiation session."""
    return SimpleNamespace(state="initialized")
