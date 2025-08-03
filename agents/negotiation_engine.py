"""
Negotiation Engine Module

Simplified negotiation engine that orchestrates buyer-seller interactions.
Moved from negotiation/ directory to simplify architecture.
"""

import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.orm import Session

from agents.buyer import BuyerAgent
from agents.seller import SellerAgent
from db.models import Quote, QuoteStatus

log = structlog.get_logger(__name__)


def build_history_log(history: list[dict]) -> str:
    """Serialise last ≤10 turns into a bullet list for prompt context."""
    return "\n".join(
        f"- {h['role']} (turn {h.get('turn',1)}): {h.get('response',h.get('price'))}"
        for h in history[-10:]
    )


@dataclass
class NegotiationState:
    """Represents the state of a negotiation."""

    state: str
    terms: dict[str, Any]
    round_number: int = 0
    last_offer: Optional[float] = None
    negotiation_history: List[Dict] = None

    def __post_init__(self):
        if self.negotiation_history is None:
            self.negotiation_history = []


class NegotiationEngine:
    """Simplified engine that manages negotiation processes between AI agents."""

    def __init__(self, seller: SellerAgent | None = None):
        """Initialize the negotiation engine."""
        self.state = "initialized"
        self.seller = seller or SellerAgent()
        self.log = structlog.get_logger(__name__)
        self.negotiation_sessions: Dict[int, NegotiationState] = {}

    async def run_loop(self, db: Session, quote_id: int) -> Quote:
        """Run initial quote pricing (first step of negotiation process)."""
        quote: Quote | None = db.get(Quote, quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        if quote.status != QuoteStatus.pending:
            raise ValueError(f"Quote {quote_id} is not in pending status")

        try:
            # Initialize negotiation session
            negotiation_state = NegotiationState(
                state="pricing",
                terms={"quote_id": quote_id},
                round_number=1,
                negotiation_history=[],
            )
            self.negotiation_sessions[quote_id] = negotiation_state

            # Initialize negotiation log
            negotiation_log = quote.negotiation_log if quote.negotiation_log else []

            # Generate initial seller quote
            seller_context = {
                "resource_type": quote.resource_type,
                "duration_hours": quote.duration_hours,
                "buyer_max_price": quote.buyer_max_price,
            }

            price = await self.seller.generate_quote(
                seller_context, negotiation_state.negotiation_history
            )

            # Log initial pricing
            pricing_entry = {
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "role": "seller",
                "price": price,
                "action": "initial_quote",
                "reasoning": f"Initial quote for {quote.resource_type} ({quote.duration_hours}h)",
            }
            negotiation_log.append(pricing_entry)

            # Update quote
            quote.price = price
            quote.status = QuoteStatus.priced
            quote.negotiation_log = negotiation_log

            # Update negotiation session
            negotiation_state.last_offer = price
            negotiation_state.negotiation_history.append(pricing_entry)

            db.add(quote)
            db.commit()

            self.log.info(
                "quote.priced",
                quote_id=quote_id,
                price=price,
                resource_type=quote.resource_type,
            )

            return quote

        except Exception as e:
            self.log.error(f"Failed to price quote {quote_id}: {str(e)}")
            raise RuntimeError(f"Quote pricing failed: {str(e)}")

    async def negotiate(
        self,
        db: Session,
        quote_id: int,
        max_turns: int = 4,
        *,
        urgency: float | None = None,
        strategy: str | None = None,
    ) -> Quote:
        """Run multi-turn negotiation between buyer and seller agents."""
        quote: Quote | None = db.get(Quote, quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        # Allow negotiation starting from pending (run initial pricing first)
        if quote.status == QuoteStatus.pending:
            quote = await self.run_loop(db, quote_id)

        if quote.status != QuoteStatus.priced:
            raise ValueError(f"Quote {quote_id} is not in priced status")

        try:
            # Initialize buyer agent with provided overrides (fallback to defaults)
            buyer = BuyerAgent(
                max_wtp=quote.buyer_max_price,
                urgency=urgency if urgency is not None else 0.7,
                strategy=strategy or "balanced",
            )

            # Get or create negotiation session
            if quote_id not in self.negotiation_sessions:
                self.negotiation_sessions[quote_id] = NegotiationState(
                    state="negotiating",
                    terms={"quote_id": quote_id},
                    round_number=1,
                    last_offer=quote.price,
                    negotiation_history=[],
                )

            negotiation_session = self.negotiation_sessions[quote_id]
            negotiation_log = quote.negotiation_log if quote.negotiation_log else []

            # Multi-turn negotiation loop
            current_price = quote.price
            turns = 0

            while turns < max_turns:
                turns += 1
                negotiation_session.round_number = turns + 1

                self.log.info(
                    "negotiation.turn_start",
                    quote_id=quote_id,
                    turn=turns,
                    current_price=current_price,
                )

                # Buyer responds to current price
                buyer_response = await buyer.respond(
                    {"price": current_price}, negotiation_session.negotiation_history
                )

                # Handle both old string format and new structured format for backward compatibility
                if isinstance(buyer_response, dict):
                    # New structured format with reasoning
                    buyer_action = buyer_response["action"]
                    buyer_price = buyer_response.get("price")
                    buyer_reason = buyer_response.get("reason")
                    response_value = (
                        "accept" if buyer_action == "accept" else str(buyer_price)
                    )
                else:
                    # Old string format for backward compatibility
                    response_value = buyer_response
                    buyer_action = (
                        "counter_offer" if buyer_response != "accept" else "accept"
                    )
                    buyer_price = (
                        float(buyer_response) if buyer_response != "accept" else None
                    )
                    buyer_reason = None

                # Log buyer response with reasoning
                buyer_entry = {
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    "role": "buyer",
                    "response": (
                        buyer_response
                        if isinstance(buyer_response, dict)
                        else response_value
                    ),
                    "action": buyer_action,
                    "turn": turns,
                }

                # Add reason if available
                if buyer_reason:
                    buyer_entry["reason"] = buyer_reason

                negotiation_log.append(buyer_entry)
                negotiation_session.negotiation_history.append(buyer_entry)

                # Check if buyer accepted
                if buyer_action == "accept":
                    quote.status = QuoteStatus.accepted
                    quote.negotiation_log = negotiation_log
                    negotiation_session.state = "accepted"

                    db.add(quote)
                    db.commit()

                    self.log.info(
                        "negotiation.accepted",
                        quote_id=quote_id,
                        final_price=current_price,
                        turns=turns,
                    )
                    break

                # Buyer made counter-offer
                try:
                    counter_price = (
                        buyer_price
                        if buyer_price is not None
                        else float(response_value)
                    )
                except (ValueError, TypeError):
                    self.log.warning(f"Invalid buyer response: {buyer_response}")
                    break

                # Seller responds to counter-offer
                seller_response = await self.seller.respond_to_counter_offer(
                    counter_price,
                    {
                        "resource_type": quote.resource_type,
                        "duration_hours": quote.duration_hours,
                        "buyer_max_price": quote.buyer_max_price,
                    },
                    negotiation_session.negotiation_history,
                )

                # Log seller response
                seller_entry = {
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    "role": "seller",
                    "response": seller_response,
                    "turn": turns,
                }
                negotiation_log.append(seller_entry)
                negotiation_session.negotiation_history.append(seller_entry)

                # Check seller action
                if seller_response["action"] == "accept":
                    quote.price = counter_price
                    quote.status = QuoteStatus.accepted
                    quote.negotiation_log = negotiation_log
                    negotiation_session.state = "accepted"
                    negotiation_session.last_offer = counter_price

                    db.add(quote)
                    db.commit()

                    self.log.info(
                        "negotiation.accepted",
                        quote_id=quote_id,
                        final_price=counter_price,
                        turns=turns,
                    )
                    break

                elif seller_response["action"] == "counter_offer":
                    current_price = seller_response["price"]
                    negotiation_session.last_offer = current_price

                    # Update quote price to reflect current negotiation state
                    quote.price = current_price
                    db.add(quote)
                    db.commit()

                elif seller_response["action"] == "reject":
                    quote.status = QuoteStatus.rejected
                    quote.negotiation_log = negotiation_log
                    negotiation_session.state = "rejected"

                    db.add(quote)
                    db.commit()

                    self.log.info(
                        "negotiation.rejected",
                        quote_id=quote_id,
                        reason=seller_response.get("reason", "Unknown"),
                        turns=turns,
                    )
                    break

            # If max turns reached without agreement
            if turns >= max_turns and quote.status == QuoteStatus.priced:
                quote.status = QuoteStatus.rejected
                quote.negotiation_log = negotiation_log
                negotiation_session.state = "max_turns_reached"

                db.add(quote)
                db.commit()

                self.log.info(
                    "negotiation.max_turns",
                    quote_id=quote_id,
                    max_turns=max_turns,
                )

            return quote

        except Exception as e:
            self.log.error(f"Failed to negotiate quote {quote_id}: {str(e)}")
            raise RuntimeError(f"Negotiation failed: {str(e)}")

    def get_negotiation_session(self, quote_id: int) -> Optional[NegotiationState]:
        """Get negotiation session for a quote."""
        return self.negotiation_sessions.get(quote_id)

    def get_active_negotiations(self) -> List[int]:
        """Get list of active negotiation quote IDs."""
        return [
            quote_id
            for quote_id, session in self.negotiation_sessions.items()
            if session.state in ["pricing", "negotiating"]
        ]

    async def finalize_negotiation(self, quote_id: int) -> dict[str, str]:
        """Complete the negotiation."""
        if quote_id in self.negotiation_sessions:
            session = self.negotiation_sessions[quote_id]
            session.state = "finalized"

            self.log.info(
                "negotiation.finalized",
                quote_id=quote_id,
                final_price=session.last_offer,
                rounds=session.round_number,
            )

        return {"status": "finalized", "state": "completed"}
