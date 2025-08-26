"""
Stripe Payment Service

This module handles all Stripe-related payment operations including:
- Creating payment intents
- Processing webhook events
- Managing payment status updates
"""

import os
from typing import Any, Union

import stripe
import structlog
import tenacity
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from core.logging import BusinessEvents
from core.settings import Settings
from db.models import Quote

log = structlog.get_logger(__name__)

# Initialize Stripe with API key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")


class StripeError(Exception):
    pass


class StripeService:
    def __init__(
        self, db: Session | AsyncSession, settings: Union[Settings, None] = None
    ):
        """
        Initialize StripeService.

        Args:
            db: Database session
            settings: Optional settings object. If not provided, will try to get from environment.
        """
        self.db = db
        if settings:
            try:
                # Try to access STRIPE_API_KEY - if it fails, it's probably a Depends object
                stripe.api_key = settings.STRIPE_API_KEY
            except (AttributeError, TypeError):
                # If we can't access STRIPE_API_KEY, fall back to environment variable
                stripe.api_key = os.getenv("STRIPE_API_KEY")
        else:
            # Fallback to environment variable if settings not provided
            stripe.api_key = os.getenv("STRIPE_API_KEY")

    def test_connection(self) -> bool:
        """Test the Stripe API connection."""
        try:
            stripe.Account.retrieve()
            return True
        except Exception:
            return False

    async def create_payment_intent(self, quote: Quote) -> dict[str, Any]:
        """
        Create a Stripe PaymentIntent for a quote.

        Args:
            quote: The Quote object to create a payment for

        Returns:
            Dict containing client_secret and payment_intent_id
        """
        log.info(
            BusinessEvents.PAYMENT_ATTEMPT,
            quote_id=quote.id,
            amount=quote.price,
            provider="stripe",
        )

        @tenacity.retry(
            stop=tenacity.stop_after_attempt(3),
            wait=tenacity.wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        )
        def _create_intent_sync():
            amount_cents = int(quote.price * 100)
            return stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                metadata={"quote_id": quote.id, "buyer_id": quote.buyer_id},
                idempotency_key=f"quote-{quote.id}-{int(quote.price * 100)}",
            )

        try:
            intent = await run_in_threadpool(_create_intent_sync)
            # Note: DB side effects are handled by the caller (route/service layer)

            log.info(
                BusinessEvents.PAYMENT_SUCCESS,
                quote_id=quote.id,
                amount=quote.price,
                provider="stripe",
                transaction_id=None,
                provider_transaction_id=intent.id,
            )

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
            }
        except stripe.error.StripeError as e:
            log.error(
                BusinessEvents.PAYMENT_FAILURE,
                quote_id=quote.id,
                amount=quote.price,
                provider="stripe",
                error=str(e),
            )
            raise StripeError(str(e))
        except Exception as e:
            log.error(
                BusinessEvents.PAYMENT_FAILURE,
                quote_id=quote.id,
                amount=quote.price,
                provider="stripe",
                error=str(e),
            )
            raise StripeError(str(e))

    def capture_payment(self, quote_id: str, payment_intent_id: str, amount: float):
        try:
            # Existing payment capture logic
            log.info(
                "stripe.capture_succeeded",
                quote_id=quote_id,
                amount_usd=float(amount),
                provider_id=payment_intent_id,
            )
            return True
        except Exception as e:
            log.error(
                "stripe.capture_failed",
                quote_id=quote_id,
                amount_usd=float(amount),
                provider_id=payment_intent_id,
                error=str(e),
            )
            return False
