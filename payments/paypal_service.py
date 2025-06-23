import os
import requests
import tenacity
from decimal import Decimal
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta, UTC
from db.models import TransactionStatus

BASE = os.getenv("PAYPAL_BASE", "https://api-m.sandbox.paypal.com")
CLIENT = os.getenv("PAYPAL_CLIENT_ID")
SECRET = os.getenv("PAYPAL_SECRET")

_TOKEN_CACHE: Tuple[str, datetime] | None = None


class PayPalError(Exception):
    pass


class PayPalService:
    def __init__(self):
        self.base = BASE
        self.client = CLIENT
        self.secret = SECRET

    def _token(self) -> str:
        global _TOKEN_CACHE
        if _TOKEN_CACHE and _TOKEN_CACHE[1] > datetime.now(UTC):
            return _TOKEN_CACHE[0]

        r = requests.post(
            f"{self.base}/v1/oauth2/token",
            auth=(self.client, self.secret),
            data={"grant_type": "client_credentials"},
        )
        r.raise_for_status()
        tok = r.json()["access_token"]
        _TOKEN_CACHE = (tok, datetime.now(UTC) + timedelta(minutes=5))
        return tok

    @staticmethod
    def map_status(paypal_status: str) -> TransactionStatus:
        """Map PayPal status to our TransactionStatus enum."""
        return (
            TransactionStatus.succeeded
            if paypal_status == "COMPLETED"
            else TransactionStatus.failed
        )

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(),
        reraise=True,
    )
    def create_and_capture(self, amount: Decimal, quote_id: int) -> Dict[str, Any]:
        """
        One-shot order create + capture to mirror Stripe immediacy.
        Returns dict with capture_id, PayPal order status, and mapped transaction status.
        """
        try:
            token = self._token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            order_body = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": f"quote-{quote_id}",
                        "amount": {"currency_code": "USD", "value": f"{amount:.2f}"},
                    }
                ],
            }
            # 1. create
            r = requests.post(
                f"{self.base}/v2/checkout/orders", json=order_body, headers=headers
            )
            r.raise_for_status()
            order_id = r.json()["id"]
            # 2. capture
            r = requests.post(
                f"{self.base}/v2/checkout/orders/{order_id}/capture", headers=headers
            )
            r.raise_for_status()
            cap = r.json()["purchase_units"][0]["payments"]["captures"][0]
            status = cap["status"]
            return {
                "capture_id": cap["id"],
                "status": status,
                "transaction_status": self.map_status(status),
            }  # status "COMPLETED" or "DECLINED"/"FAILED"
        except requests.RequestException as e:
            raise PayPalError(f"PayPal settlement failed: {e}")
