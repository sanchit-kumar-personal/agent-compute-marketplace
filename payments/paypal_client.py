import paypalrestsdk
from fastapi import Depends
from core.settings import Settings
from main import get_settings


class PayPalClient:
    def __init__(self, settings: Settings = Depends(get_settings)):
        paypalrestsdk.configure(
            {
                "mode": "sandbox",  # Change to "live" in production
                "client_id": settings.PAYPAL_CLIENT_ID,
                "client_secret": settings.PAYPAL_SECRET,
            }
        )

    def test_connection(self) -> bool:
        """Test the PayPal API connection."""
        try:
            # Just verify credentials by getting payment list
            paypalrestsdk.Payment.all({"count": 1})
            return True
        except Exception:
            return False
