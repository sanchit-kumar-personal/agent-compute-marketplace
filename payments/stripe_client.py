import stripe
from fastapi import Depends
from core.settings import Settings
from main import get_settings


class StripeClient:
    def __init__(self, settings: Settings = Depends(get_settings)):
        stripe.api_key = settings.STRIPE_KEY

    def test_connection(self) -> bool:
        """Test the Stripe API connection."""
        try:
            stripe.Account.retrieve()
            return True
        except Exception:
            return False
