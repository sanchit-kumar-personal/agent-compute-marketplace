"""
BuyerAgent Module

This module implements an advanced buyer agent that can negotiate prices for compute resources.
The agent uses sophisticated strategies based on urgency, budget constraints, and market conditions.
"""

import json
import structlog
from typing import Dict, List

from core.llm import get_llm
from core.llm_utils import call_llm_with_retry, BuyerReply

log = structlog.get_logger(__name__)


class BuyerAgent:
    """Advanced buyer agent with sophisticated negotiation strategies."""

    def __init__(
        self,
        max_wtp: float,
        urgency: float = 0.7,  # Increased default urgency for more active negotiation
        strategy: str = "balanced",
        budget_flexibility: float = 0.25,  # Increased from 0.1 - now 25% flexibility for realistic deals
    ):
        """
        Initialize buyer agent with enhanced negotiation capabilities.

        Args:
            max_wtp: Maximum willingness to pay
            urgency: How urgent the need is (0-1), affects negotiation strategy
            strategy: Negotiation strategy ('aggressive', 'balanced', 'conservative')
            budget_flexibility: How much above max_wtp willing to go in urgent situations
        """
        self.max_wtp = max_wtp
        self.urgency = urgency
        self.strategy = strategy
        self.budget_flexibility = budget_flexibility
        self.negotiation_history: List[Dict] = []
        self.llm = get_llm()

        # Calculate effective maximum based on urgency and flexibility
        self.effective_max = max_wtp * (1 + budget_flexibility * urgency)

    async def respond(self, quote: dict, history: list[dict] = None) -> str | dict:
        """
        Generate sophisticated response to seller's quote using AI and strategy.

        Args:
            quote: Dictionary containing quote details including price
            history: Negotiation history for context

        Returns:
            Response string ('accept' or counter-offer price) for backward compatibility,
            or structured dict with action, price, and reason for detailed logging
        """
        if history is None:
            history = []

        seller_price = quote["price"]

        # Record this offer in negotiation history
        self.negotiation_history.append(
            {
                "type": "seller_offer",
                "price": seller_price,
                "round": len(self.negotiation_history) + 1,
            }
        )

        # Early acceptance for very good deals
        if seller_price <= self.max_wtp * 0.6:  # If price is 60% or less of our budget
            log.info(
                "buyer.early_accept_great_deal",
                seller_price=seller_price,
                max_wtp=self.max_wtp,
            )
            return {
                "action": "accept",
                "price": None,
                "reason": "Excellent price, well within budget",
            }

        # Accept within budget after multiple rounds - but only if it's a reasonable deal
        if (
            len(self.negotiation_history)
            >= 4  # Increased to 4 rounds to be less aggressive
            and seller_price <= self.max_wtp * 0.95  # Must be at least 5% under budget
        ):
            return {
                "action": "accept",
                "price": None,
                "reason": "Acceptable price after extended negotiation",
            }

        # Check enhanced negotiation acceptance logic
        if self._should_accept_in_negotiation(seller_price):
            return {
                "action": "accept",
                "price": None,
                "reason": "Price meets acceptance criteria",
            }

        # Use AI for sophisticated negotiation with history context
        log.info(
            "buyer.negotiation_attempt",
            quote_id=quote.get("id", "unknown"),
            seller_price=seller_price,
            strategy=self.strategy,
            urgency=self.urgency,
            round=len(self.negotiation_history),
        )
        try:

            # Build negotiation context
            negotiation_context = self._build_negotiation_context(history, seller_price)

            system_prompt = f"""
You are a STRATEGIC buyer negotiating for cloud compute resources.

YOUR PROFILE:
- Maximum budget: ${self.max_wtp}
- Effective max (emergency): ${self.effective_max}
- Urgency level: {self.urgency}/1.0 (higher = more urgent)
- Strategy: {self.strategy}
- Current round: {len(self.negotiation_history)}

CRITICAL NEGOTIATION RULES:
1. NEVER bid above the seller's current asking price
2. NEVER bid above your maximum budget (${self.max_wtp})
3. ALWAYS move progressively toward the seller (don't decrease your offers)
4. Consider accepting after 3+ rounds if price is within budget

BIDDING STRATEGY:
- First round: Start 15-25% below seller's ask (but above 60% of your budget)
- Later rounds: Move halfway toward seller's current price
- If seller is compromising, show good faith by moving closer
- If seller holds firm repeatedly, consider accepting if within budget

{negotiation_context}

CURRENT DECISION:
- Seller is asking: ${seller_price}
- Your budget allows: ${self.max_wtp}
- This is round: {len(self.negotiation_history) + 1}

RESPONSE RULES:
- If seller's price ≤ your budget AND you've negotiated 4+ rounds AND it's a good deal: consider accepting
- NEVER accept if price > your maximum budget (${self.max_wtp}) under any circumstances
- If making counter-offer: price must be < ${seller_price} and ≤ ${self.max_wtp}
- Show progress toward agreement with each round
- If price is above budget, always counter-offer or reject, never accept

Reply in JSON exactly matching this schema:
{{"action": "accept|counter_offer", "price": <number or null>, "reason": "<brief explanation of your decision>"}}
"""

            msg = json.dumps(
                {
                    "seller_price": seller_price,
                    "max_budget": self.max_wtp,
                    "effective_max": self.effective_max,
                    "urgency": self.urgency,
                    "negotiation_round": len(self.negotiation_history),
                    "strategy": self.strategy,
                    "budget_flexibility": self.budget_flexibility,
                }
            )

            result = await call_llm_with_retry(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": msg},
                ],
                BuyerReply,
                self.llm,
            )

            # Return based on validated result
            if result.action == "accept":
                # CRITICAL: Double-check that we never accept above budget, even if LLM suggests it
                if seller_price > self.max_wtp:
                    log.warning(
                        "buyer.llm_tried_to_accept_above_budget",
                        seller_price=seller_price,
                        max_wtp=self.max_wtp,
                        llm_reason=result.reason,
                    )
                    # Override LLM decision and counter-offer instead
                    counter = self._generate_strategic_counter_offer(seller_price)
                    final_counter = min(counter, seller_price - 0.01)
                    final_counter = round(max(0.01, final_counter), 2)
                    return {
                        "action": "counter_offer",
                        "price": final_counter,
                        "reason": f"LLM suggested accept, but price ${seller_price} exceeds budget ${self.max_wtp}. Counter-offering instead.",
                    }

                log.info(
                    "buyer.llm_decision",
                    decision="accept",
                    seller_price=seller_price,
                    reason=result.reason,
                )
                return {
                    "action": "accept",
                    "price": None,
                    "reason": result.reason or "Seller's price is acceptable",
                }
            else:
                # Clamp to ensure we never bid above seller ask
                safe_price = min(result.price, seller_price - 0.01)
                final_price = round(max(0.01, safe_price), 2)
                log.info(
                    "buyer.llm_decision",
                    decision="counter_offer",
                    seller_price=seller_price,
                    llm_suggested=result.price,
                    final_clamped=final_price,
                    reason=result.reason,
                )
                return {
                    "action": "counter_offer",
                    "price": final_price,
                    "reason": result.reason or f"Counter-offering ${final_price}",
                }

        except Exception as e:
            # Fallback to deterministic logic
            log.warning(
                "buyer.llm_failed_fallback_deterministic",
                error=str(e),
                error_type=type(e).__name__,
                seller_price=seller_price,
            )
            counter = self._generate_strategic_counter_offer(seller_price)
            # Ensure we never counter above seller's current price
            counter = min(counter, seller_price - 0.01)
            final_counter = round(max(0.01, counter), 2)
            log.info(
                "buyer.deterministic_decision",
                seller_price=seller_price,
                counter_offer=final_counter,
            )
            return {
                "action": "counter_offer",
                "price": final_counter,
                "reason": f"Strategic counter-offer using {self.strategy} strategy",
            }

    def _should_accept_in_negotiation(self, seller_price: float) -> bool:
        """Enhanced acceptance logic for ongoing negotiations."""
        rounds = len(self.negotiation_history)

        # Accept after 4+ rounds when well within budget (5% buffer)
        if rounds >= 4 and seller_price <= self.max_wtp * 0.95:
            return True

        return False

    def _build_negotiation_prompt(self, quote: dict) -> str:
        """Build sophisticated negotiation prompt for AI."""
        return f"""
        You are a sophisticated buyer negotiating for cloud compute resources.

        Your Profile:
        - Maximum budget: ${self.max_wtp}
        - Urgency level: {self.urgency}/1.0 (higher = more urgent)
        - Strategy: {self.strategy}
        - Negotiation round: {len(self.negotiation_history)}

        Negotiation Guidelines:
        - If price is within budget and reasonable, accept
        - Be strategic: don't accept first offer unless exceptional
        - Consider market conditions and negotiation history
        - Use your strategy: aggressive (low offers), balanced (fair offers), conservative (close to asking)
        - Factor in negotiation round: be more flexible in later rounds

        Response Format:
        - If accepting: respond with "accept"
        - If counter-offering: respond with ONLY a number (your counter-offer price)
        - Do not include currency symbols or explanations

        Current offer: ${quote["price"]}
        Your analysis: {self._analyze_offer(quote)}
        """

    def _analyze_offer(self, quote: dict) -> str:
        """Analyze the seller's offer and provide context for negotiation."""
        price = quote.get("price", 0)
        reason = quote.get("reason", "No reason provided")

        if price <= self.max_wtp * 0.8:
            analysis = f"Good deal at ${price} - within comfortable budget."
        elif price <= self.max_wtp:
            analysis = (
                f"Acceptable at ${price} - within max budget but room to negotiate."
            )
        elif price <= self.effective_max:
            analysis = f"Above budget at ${price} but within emergency range."
        else:
            analysis = f"Too expensive at ${price} - exceeds maximum willing to pay."

        return f"{analysis} Seller's reasoning: {reason}"

    def _build_negotiation_context(
        self, history: list[dict], current_seller_price: float
    ) -> str:
        """Build rich negotiation context for LLM prompt."""
        if not history:
            return f"""
NEGOTIATION HISTORY: (This is the first offer)
- Seller's opening ask: ${current_seller_price}
- Your task: Make a strategic counter-offer 15-25% below their ask
"""

        # Extract key offers from history
        context_lines = ["NEGOTIATION HISTORY:"]
        my_last_offer = None
        seller_movement = []

        for i, turn in enumerate(history[-5:], 1):  # Last 5 turns max
            role = turn.get("role", "unknown")
            if role == "seller":
                price = turn.get("price", turn.get("response", {}).get("price", 0))
                seller_movement.append(price)
                context_lines.append(f"- Round {i}: Seller asked ${price}")
            elif role == "buyer":
                response = turn.get("response", "")
                if response != "accept":
                    try:
                        price = float(response.get("price", 0))
                        my_last_offer = price
                        context_lines.append(f"- Round {i}: You offered ${price}")
                    except (ValueError, TypeError, AttributeError):
                        context_lines.append(f"- Round {i}: You {response}")

        # Add seller movement analysis
        if len(seller_movement) >= 2:
            if seller_movement[-1] < seller_movement[-2]:
                context_lines.append(
                    f"- SELLER IS COMPROMISING: moved from ${seller_movement[-2]} to ${seller_movement[-1]}"
                )
            elif seller_movement[-1] == seller_movement[-2]:
                context_lines.append(
                    f"- SELLER HOLDING FIRM: repeated ${seller_movement[-1]}"
                )

        # Add strategic guidance
        context_lines.append(f"\nCURRENT SELLER ASK: ${current_seller_price}")

        if my_last_offer:
            context_lines.append(f"YOUR LAST OFFER: ${my_last_offer}")
            if current_seller_price < my_last_offer:
                context_lines.append(
                    "⚠️  SELLER'S CURRENT ASK IS BELOW YOUR LAST OFFER - Consider accepting!"
                )
            else:
                target = my_last_offer + (current_seller_price - my_last_offer) * 0.5
                context_lines.append(
                    f"SUGGESTED NEXT OFFER: ~${target:.2f} (move halfway toward seller)"
                )
        else:
            target = max(current_seller_price * 0.8, self.max_wtp * 0.6)
            context_lines.append(
                f"SUGGESTED FIRST OFFER: ~${target:.2f} (15-25% below seller ask)"
            )

        return "\n".join(context_lines)

    def _generate_strategic_counter_offer(self, seller_price: float) -> float:
        """Generate strategic counter-offer that increases each round toward middle ground."""
        negotiation_round = len(self.negotiation_history)

        # New progressive counter offer based directly on seller price to ensure movement toward agreement
        if negotiation_round == 0:
            # Start 20-25% below seller ask but not below 50% of max budget
            counter = max(seller_price * 0.8, self.max_wtp * 0.5)
        else:
            # Move halfway toward seller's current price each additional round
            previous = getattr(self, "last_offer", seller_price * 0.8)
            counter = previous + (seller_price - previous) * 0.5

        # Apply urgency boost (more urgency ⇒ offer more)
        counter *= 1 + self.urgency * 0.05

        # Cap by budget & effective max
        counter = min(counter, self.effective_max)

        # Ensure still below seller price (at least 1c difference)
        counter = min(counter, seller_price - 0.01)

        # Round to cents
        final_counter = round(max(0.01, counter), 2)

        # Store for future rounds
        self.last_offer = final_counter

        return final_counter

    async def make_offer(self) -> dict:
        """
        Generate initial offer based on maximum willingness to pay and strategy.

        Returns:
            dict: Initial offer with price and reasoning
        """
        # Strategic initial offer based on strategy
        if self.strategy == "aggressive":
            # Start low to leave room for negotiation
            initial_price = self.max_wtp * (0.5 + (0.2 * self.urgency))
        elif self.strategy == "conservative":
            # Start closer to max budget
            initial_price = self.max_wtp * (0.8 + (0.1 * self.urgency))
        else:  # balanced
            # Start in the middle
            initial_price = self.max_wtp * (0.65 + (0.15 * self.urgency))

        return {
            "price": round(initial_price, 2),
            "strategy": self.strategy,
            "urgency": self.urgency,
            "reasoning": f"Initial {self.strategy} offer with urgency factor {self.urgency}",
        }

    def should_accept_offer(self, price: float) -> bool:
        """Determine if an offer should be accepted based on current situation."""
        # Always accept if within original budget and we've negotiated multiple rounds
        if price <= self.max_wtp and len(self.negotiation_history) >= 2:
            return True

        # Accept if within effective max and urgency is high after some negotiation
        if (
            price <= self.effective_max
            and self.urgency > 0.5
            and len(self.negotiation_history) >= 1
        ):
            return True

        # Accept if we've been negotiating for a while and price is reasonable
        if len(self.negotiation_history) >= 3 and price <= self.max_wtp * 1.1:
            return True

        return False

    def get_negotiation_stats(self) -> dict:
        """Get statistics about current negotiation session."""
        if not self.negotiation_history:
            return {"rounds": 0, "avg_price": 0, "trend": "none"}

        prices = [h["price"] for h in self.negotiation_history if "price" in h]
        return {
            "rounds": len(self.negotiation_history),
            "avg_price": sum(prices) / len(prices) if prices else 0,
            "lowest_offer": min(prices) if prices else 0,
            "latest_offer": prices[-1] if prices else 0,
            "trend": (
                "decreasing"
                if len(prices) > 1 and prices[-1] < prices[0]
                else "increasing"
            ),
        }
