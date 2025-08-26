import json
import logging
import random
import structlog
from typing import Any, Dict, List

from core.llm import get_llm
from core.llm_utils import call_llm_with_retry, SellerReply

logger = logging.getLogger(__name__)
log = structlog.get_logger(__name__)

# Enhanced pricing model with market dynamics - REALISTIC market rates
BASE_PRICES = {
    "GPU": {
        "base": 2.5,  # Reduced from 8.0 - now $2.50/hr (realistic AWS/GCP rates)
        "demand_multiplier": 1.2,  # Reduced from 1.8
        "scarcity_threshold": 0.8,
    },
    "CPU": {
        "base": 0.8,  # Reduced from 3.0 - now $0.80/hr (realistic rates)
        "demand_multiplier": 1.1,  # Reduced from 1.4
        "scarcity_threshold": 0.9,
    },
    "TPU": {
        "base": 6.0,  # Reduced from 15.0 - now $6.00/hr (realistic rates)
        "demand_multiplier": 1.3,  # Reduced from 2.2
        "scarcity_threshold": 0.7,
    },
}

# Market conditions simulation - more moderate
MARKET_CONDITIONS = {
    "high_demand": 1.2,  # Reduced from 1.3
    "normal": 1.0,
    "low_demand": 0.9,  # Increased from 0.8 for less extreme swings
}


class SellerAgent:
    """Advanced seller agent with market awareness and negotiation strategies."""

    def __init__(
        self,
        strategy: str = "balanced",
        min_margin: float = 0.05,  # Reduced from 0.1 - now 5% minimum (more flexible)
        max_discount: float = 0.4,  # Increased from 0.3 - now 40% max discount (more generous)
        market_condition: str = "normal",
        seed: int = None,  # For deterministic testing
    ):
        """
        Initialize seller agent with configurable strategy.

        Args:
            strategy: Negotiation strategy ('aggressive', 'balanced', 'conservative')
            min_margin: Minimum profit margin to maintain
            max_discount: Maximum discount willing to offer
            market_condition: Current market condition ('high_demand', 'normal', 'low_demand')
            seed: Random seed for deterministic behavior in tests
        """
        self.strategy = strategy
        self.min_margin = min_margin
        self.max_discount = max_discount
        self.market_condition = market_condition
        self.negotiation_history: List[Dict] = []
        self._random = random.Random(seed) if seed is not None else random

    def get_market_multiplier(self) -> float:
        """Get current market condition multiplier."""
        return MARKET_CONDITIONS.get(self.market_condition, 1.0)

    def calculate_resource_scarcity(self, resource_type: str) -> float:
        """Calculate resource scarcity based on real utilization."""
        try:
            # Import here to avoid circular imports
            from api.routes.resources import (
                BASE_RESOURCE_CONFIG,
                get_current_availability,
            )

            if resource_type.upper() in BASE_RESOURCE_CONFIG:
                config = BASE_RESOURCE_CONFIG[resource_type.upper()]
                available = get_current_availability(resource_type.upper(), config)
                total = config["total_units"]
                scarcity = 1.0 - (available / total)
                return round(max(0.0, min(1.0, scarcity)), 2)
        except Exception:
            # Fallback to moderate scarcity if import fails
            pass

        # Fallback to moderate scarcity
        return 0.7

    def get_base_price(self, resource_type: str, duration_hours: int) -> float:
        """Calculate base price with market dynamics."""
        resource_config = BASE_PRICES.get(resource_type.upper(), BASE_PRICES["CPU"])
        base_price = resource_config["base"]

        # Apply market conditions
        market_multiplier = self.get_market_multiplier()

        # Apply scarcity premium
        scarcity = self.calculate_resource_scarcity(resource_type)
        if scarcity > resource_config["scarcity_threshold"]:
            scarcity_multiplier = (
                1 + (scarcity - resource_config["scarcity_threshold"]) * 2
            )
        else:
            scarcity_multiplier = 1.0

        # Apply duration discounts for longer commitments
        duration_discount = 1.0
        if duration_hours >= 168:  # 1 week
            duration_discount = 0.9  # 10% discount for 1+ week
        elif duration_hours >= 24:
            duration_discount = 0.95  # 5% discount for 24+ hours

        # Apply REALISTIC negotiation premium - start 10-20% higher for reasonable positioning
        negotiation_premium = self._random.uniform(1.1, 1.2)  # Reduced from 1.4-1.6

        total_price = (
            base_price
            * duration_hours
            * market_multiplier
            * scarcity_multiplier
            * duration_discount
            * negotiation_premium
        )

        # Cap total markup to prevent unrealistic pricing (max 50% above base)
        max_price = base_price * duration_hours * 1.5
        total_price = min(total_price, max_price)

        return round(total_price, 2)

    def _build_negotiation_prompt(self, quote: dict[str, Any]) -> str:
        """Build seller negotiation prompt inline (consistent with buyer agent)."""
        return f"""
        You are an AI-powered cloud compute resource seller with sophisticated pricing capabilities.

        Your Profile:
        - Strategy: {self.strategy}
        - Market condition: {self.market_condition}
        - Minimum margin: {self.min_margin * 100}%
        - Maximum discount: {self.max_discount * 100}%
        - Negotiation round: {len(self.negotiation_history)}

        Current Request:
        - Resource: {quote['resource_type']}
        - Duration: {quote['duration_hours']} hours
        - Buyer max budget: ${quote.get('buyer_max_price', 0)}
        - Resource scarcity: {self.calculate_resource_scarcity(quote['resource_type']):.2f}

        Pricing Guidelines:
        - Base rates: GPU=$2.50/hr, CPU=$0.80/hr, TPU=$6.00/hr
        - Apply market conditions and scarcity premiums
        - Consider buyer's budget but maintain profitability
        - Use strategy: aggressive (high margins), balanced (competitive), conservative (market rate)
        - Offer volume discounts for 24+ hour commitments

        Response Format:
        - Respond with ONLY a number (total price for entire duration)
        - No currency symbols, explanations, or additional text
        - Price should be competitive but profitable

        Market Analysis: {self._analyze_market_context(quote)}
        """

    def _analyze_market_context(self, quote: dict[str, Any]) -> str:
        """Analyze current market context for the prompt."""
        base_price = self.get_base_price(
            quote["resource_type"], quote["duration_hours"]
        )
        buyer_budget = quote.get("buyer_max_price", 0)

        if buyer_budget > base_price * 1.2:
            return "Buyer budget allows for premium pricing"
        elif buyer_budget < base_price * 0.8:
            return "Buyer budget is tight, consider competitive pricing"
        else:
            return "Buyer budget is reasonable, standard pricing appropriate"

    def _build_seller_negotiation_context(
        self, history: list[dict], base_price: float, quote: dict
    ) -> str:
        """Build rich negotiation context for seller LLM prompt."""
        if not history:
            return f"""
NEGOTIATION HISTORY: (This is your opening quote)
- Your base cost: ${base_price:.2f}
- Your task: Offer a competitive but profitable opening price
"""

        # Extract negotiation flow
        context_lines = ["NEGOTIATION HISTORY:"]
        buyer_offers = []
        my_last_price = None

        for i, turn in enumerate(history[-5:], 1):  # Last 5 turns
            role = turn.get("role", "unknown")
            if role == "buyer":
                response = turn.get("response", "")
                if response != "accept":
                    try:
                        price = float(response)
                        buyer_offers.append(price)
                        context_lines.append(f"- Round {i}: Buyer offered ${price}")
                    except (ValueError, TypeError):
                        context_lines.append(f"- Round {i}: Buyer {response}")
            elif role == "seller":
                price = turn.get("price", turn.get("response", {}).get("price", 0))
                my_last_price = price
                context_lines.append(f"- Round {i}: You asked ${price}")

        # Analyze buyer movement
        if len(buyer_offers) >= 2:
            if buyer_offers[-1] > buyer_offers[-2]:
                context_lines.append(
                    f"- BUYER IS MOVING UP: increased from ${buyer_offers[-2]} to ${buyer_offers[-1]}"
                )
            elif buyer_offers[-1] == buyer_offers[-2]:
                context_lines.append(
                    f"- BUYER HOLDING FIRM: repeated ${buyer_offers[-1]}"
                )

        # Strategic recommendations
        context_lines.append("\nYOUR COSTS & MARGINS:")
        context_lines.append(f"- Base cost: ${base_price:.2f}")
        context_lines.append(
            f"- Minimum acceptable: ${base_price * (1 + self.min_margin):.2f}"
        )

        if buyer_offers:
            latest_buyer_offer = buyer_offers[-1]
            context_lines.append(f"\nBUYER'S LATEST OFFER: ${latest_buyer_offer}")

            if latest_buyer_offer >= base_price * (1 + self.min_margin):
                context_lines.append(
                    "✅ BUYER'S OFFER MEETS YOUR MINIMUM - Consider accepting!"
                )
            else:
                if my_last_price:
                    target = my_last_price - (my_last_price - latest_buyer_offer) * 0.4
                    context_lines.append(
                        f"SUGGESTED COUNTER: ~${target:.2f} (move toward buyer)"
                    )
                else:
                    context_lines.append(
                        "CONSIDER: Small concession to keep negotiation alive"
                    )

        return "\n".join(context_lines)

    async def generate_quote(
        self, quote: dict[str, Any], history: list[dict] = None
    ) -> float:
        """Generate a quote price using AI negotiation or fallback pricing."""
        if history is None:
            history = []

        log.info(
            "seller.quote_generation",
            resource_type=quote.get("resource_type", "unknown"),
            duration_hours=quote.get("duration_hours", 0),
            buyer_max_price=quote.get("buyer_max_price", 0),
            market_condition=self.market_condition,
            strategy=self.strategy,
        )

        try:
            llm = get_llm()

            # Build negotiation context
            base_price = self.get_base_price(
                quote["resource_type"], quote["duration_hours"]
            )
            negotiation_context = self._build_seller_negotiation_context(
                history, base_price, quote
            )

            system_prompt = f"""
You are a STRATEGIC cloud compute resource seller who wants to close profitable deals.

YOUR PROFILE:
- Strategy: {self.strategy}
- Market condition: {self.market_condition}
- Base cost: ${base_price:.2f} for this request
- Minimum margin: {self.min_margin * 100}% (${base_price * (1 + self.min_margin):.2f} minimum)
- Maximum discount: {self.max_discount * 100}% (${base_price * (1 - self.max_discount):.2f} floor)

CRITICAL NEGOTIATION RULES:
1. NEVER go below your minimum margin price (${base_price * (1 + self.min_margin):.2f})
2. MOVE toward buyer's price each round to show good faith
3. Consider buyer's budget (${quote.get('buyer_max_price', 0)}) - don't price them out
4. Accept reasonable offers after 3+ rounds of negotiation

PRICING STRATEGY:
- If buyer is reasonable, move halfway toward their offer each round
- If buyer lowballs, counter with small concessions
- If close to their budget, consider accepting to close the deal
- Show progression toward agreement

{negotiation_context}

CURRENT DECISION:
- Base cost: ${base_price:.2f}
- Buyer's budget: ${quote.get('buyer_max_price', 0)}
- Your minimum: ${base_price * (1 + self.min_margin):.2f}

RESPONSE RULES:
- If buyer's offer ≥ your minimum margin: strongly consider accepting
- If making counter-offer: show movement toward buyer's price
- Be realistic about market rates and buyer constraints

Reply in JSON exactly matching this schema:
{{"action": "accept|counter_offer|reject", "price": <number or null>, "reason": "<brief explanation>"}}
"""

            # Build context message
            user_message = json.dumps(
                {
                    "resource_type": quote["resource_type"],
                    "duration_hours": quote["duration_hours"],
                    "buyer_max_price": quote.get("buyer_max_price", 0),
                    "market_condition": self.market_condition,
                    "negotiation_round": len(self.negotiation_history),
                }
            )

            result = await call_llm_with_retry(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                SellerReply,
                llm,
            )

            # Return price from AI response
            log.info(
                "seller.llm_quote_decision",
                llm_suggested=result.price,
                base_price_calculation=base_price,
            )
            return result.price

        except Exception as e:
            # Fallback to base pricing if AI fails
            log.warning(
                "seller.llm_failed_fallback_base_price",
                error=str(e),
                error_type=type(e).__name__,
            )
            fallback_price = self.get_base_price(
                quote["resource_type"], quote["duration_hours"]
            )
            log.info("seller.base_price_decision", fallback_price=fallback_price)
            return fallback_price

    async def respond_to_counter_offer(
        self,
        counter_price: float,
        original_quote: dict[str, Any],
        history: list[dict] = None,
    ) -> dict[str, Any]:
        """Respond to buyer's counter-offer with REALISTIC middle ground negotiation."""
        if history is None:
            history = []

        base_price = self.get_base_price(
            original_quote["resource_type"], original_quote["duration_hours"]
        )
        min_acceptable = base_price * (1 + self.min_margin)
        negotiation_round = len(history)

        # REALISTIC negotiation: Accept reasonable offers quickly
        if counter_price >= min_acceptable:
            return {
                "action": "accept",
                "price": counter_price,
                "reason": "Good margin achieved - deal closed!",
            }

        # Move toward middle ground with each round
        if negotiation_round > 0:
            # Get our last offer from history
            last_seller_price = None
            for entry in reversed(history):
                if entry.get("role") == "seller" and "response" in entry:
                    if (
                        isinstance(entry["response"], dict)
                        and "price" in entry["response"]
                    ):
                        last_seller_price = entry["response"]["price"]
                        break

            if last_seller_price:
                # Move 50% toward buyer's offer each round (realistic convergence)
                middle_ground = (
                    last_seller_price - (last_seller_price - counter_price) * 0.5
                )
                new_price = max(middle_ground, min_acceptable)
            else:
                # First counter-offer: start closer to market
                new_price = base_price * 1.15  # Only 15% above base
        else:
            new_price = base_price * 1.15  # Start only 15% above base

        # Accept after 3 rounds if buyer is close to minimum
        if negotiation_round >= 3 and counter_price >= min_acceptable * 0.95:
            return {
                "action": "accept",
                "price": counter_price,
                "reason": "Close enough after several rounds - let's close this deal!",
            }

        # If gap is still too large, try AI negotiation
        if counter_price >= base_price * 0.6:
            try:
                from agents.negotiation_engine import build_history_log

                llm = get_llm()

                system_prompt = f"""
You are a REALISTIC seller negotiating cloud compute resources.

Your Profile:
- Strategy: {self.strategy}
- Minimum margin: {self.min_margin * 100}% (flexible)
- Current round: {negotiation_round}

REALISTIC BEHAVIOR:
- MOVE DOWN toward buyer's price each round
- Find middle ground that works for both parties
- Accept reasonable deals - don't let good business slip away
- Show flexibility and willingness to close

Conversation so far:
{build_history_log(history)}

Buyer offered: ${counter_price}
Your minimum acceptable: ${min_acceptable}
Market rate: {base_price}

GOAL: Find a compromise price that works for both parties!

Reply in JSON exactly matching this schema:
{{"action": "accept|counter_offer", "price": <number or null>, "reason": "<explanation>"}}
"""

                user_message = json.dumps(
                    {
                        "counter_price": counter_price,
                        "min_acceptable": min_acceptable,
                        "base_price": base_price,
                        "negotiation_round": negotiation_round,
                    }
                )

                result = await call_llm_with_retry(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    SellerReply,
                    llm,
                )

                # Ensure AI price moves toward buyer (doesn't go higher)
                if result.action == "counter_offer" and result.price:
                    # Cap at our calculated middle ground price
                    capped_price = min(result.price, new_price)
                    return {
                        "action": result.action,
                        "price": capped_price,
                        "reason": result.reason,
                    }
                else:
                    return {
                        "action": result.action,
                        "price": result.price,
                        "reason": result.reason,
                    }

            except Exception:
                # Fallback to middle ground logic
                pass

        return {
            "action": "counter_offer",
            "price": round(new_price, 2),
            "reason": f"Moving toward middle ground (round {negotiation_round + 1})",
        }
