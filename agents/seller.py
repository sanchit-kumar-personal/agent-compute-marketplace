import json
import logging
from pathlib import Path
from core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
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
            float: Calculated price for the quote

        Note:
            Will attempt to use LLM for dynamic pricing, but falls back to
            deterministic pricing if LLM fails or returns invalid response.
        """
        try:
            llm = get_llm()
            system_msg = SYSTEM_PROMPT.read_text()
            user_msg = json.dumps(
                {
                    "resource_type": quote["resource_type"],
                    "duration_hours": quote["duration_hours"],
                }
            )

            response = await llm.ainvoke(
                [
                    SystemMessage(content=system_msg),
                    HumanMessage(content=user_msg),
                ]
            )
            price = float(response.content.strip())
            if price <= 0:
                raise ValueError("LLM returned non-positive price")
            return price

        except Exception as e:
            logger.warning(
                f"Failed to generate price with LLM: {e}. Using fallback pricing."
            )
            # Fallback to deterministic pricing
            base_price = BASE_PRICES.get(quote["resource_type"].upper(), 1.0)
            return base_price * quote["duration_hours"]
