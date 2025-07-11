"""
BuyerAgent Module

This module implements a buyer agent that can negotiate prices for compute resources.
The agent accepts if the price is below max willingness to pay, otherwise makes counter-offers.
"""

import json

from core.llm import get_llm


class BuyerAgent:
    """Accepts if price ≤ max_wtp, else proposes counter-offer."""

    def __init__(self, max_wtp: float, urgency: float = 0.5):
        """
        Initialize buyer agent.

        Args:
            max_wtp: Maximum willingness to pay
            urgency: How urgent the need is (0-1), affects negotiation strategy
        """
        self.max_wtp = max_wtp
        self.urgency = urgency
        self.llm = get_llm()

    async def respond(self, quote: dict) -> str:
        """
        Generate response to seller's quote.

        Args:
            quote: Dictionary containing quote details including price

        Returns:
            Response string ('accept' or counter-offer price)
        """
        prompt = (
            f"You are a buyer. If seller price is <= {self.max_wtp}, reply 'accept'. "
            "Otherwise reply with a lower numeric counter offer. "
            "Never explain."
        )

        msg = json.dumps({"seller_price": quote["price"]})

        response = await self.llm.ainvoke(
            [{"role": "system", "content": prompt}, {"role": "user", "content": msg}]
        )

        return response.content.strip()

    async def make_offer(self) -> dict:
        """
        Generate initial offer based on maximum willingness to pay.

        Returns:
            dict: Initial offer with price
        """
        # Start with a price below max_wtp based on urgency
        initial_price = self.max_wtp * (
            0.7 + (0.2 * self.urgency)
        )  # Between 70-90% of max_wtp
        return {"price": round(initial_price, 2)}
