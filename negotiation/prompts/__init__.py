"""
Negotiation Prompts Package

This package contains the GPT prompts and templates used in the negotiation process.
These prompts guide the AI agents in generating appropriate responses during:
- Initial offer creation
- Counter-offer evaluation
- Deal term negotiation
- Final acceptance/rejection decisions
"""

from typing import Dict

# Template mapping for different negotiation stages
PROMPT_TEMPLATES: Dict[str, str] = {
    "initial_offer": "",  # Template for generating initial offers
    "counter_offer": "",  # Template for generating counter-offers
    "evaluation": "",  # Template for evaluating offers
    "final_terms": "",  # Template for finalizing deal terms
}
