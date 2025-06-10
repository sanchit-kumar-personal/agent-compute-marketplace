import json
import logging
from pathlib import Path
from core.llm import get_llm
from typing import Dict, Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    Path(__file__).parent.parent / "negotiation" / "prompts" / "seller_system.txt"
)

# Base pricing for different resource types (per hour)
BASE_PRICES = {
    "GPU": 2.0,
    "CPU": 0.5,
    "TPU": 5.0,
}


class SellerAgent:
    async def generate_quote(self, quote: Dict[str, Any]) -> float:
        """Generate a quote price using LLM or fallback to deterministic pricing.

        Args:
            quote: Quote details including resource_type and duration_hours

        Returns:
            float: Calculated total price for the quote duration
        """
        try:
            llm = get_llm()
            system_msg = SYSTEM_PROMPT.read_text()

            # Only include relevant fields for pricing
            quote_data = {
                "resource_type": quote["resource_type"],
                "duration_hours": quote["duration_hours"],
            }
            if "counter_price" in quote:
                quote_data["counter_price"] = quote["counter_price"]

            user_msg = json.dumps(quote_data)

            response = await llm.ainvoke(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ]
            )

            try:
                price = float(response.content)
                logger.info(f"LLM generated price: {price}")
                return price
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid LLM response, falling back to deterministic pricing"
                )
                pass

        except Exception as e:
            logger.warning(
                f"LLM error: {str(e)}, falling back to deterministic pricing"
            )

        # Fallback to deterministic pricing
        base_price = BASE_PRICES.get(quote["resource_type"].upper(), 1.0)
        total_price = base_price * quote["duration_hours"]
        logger.info(
            f"Using base pricing: {base_price} * {quote['duration_hours']} = {total_price}"
        )
        return total_price
