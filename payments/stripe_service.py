"""
Stripe Payment Service

This module handles all Stripe-related payment operations including:
- Creating payment intents
- Processing webhook events
- Managing payment status updates
"""

import os
import stripe
from typing import Dict, Any, Optional, Union
from db.models import Transaction, Quote, PaymentProvider
from sqlalchemy.orm import Session
from core.settings import Settings
from fastapi import Depends
import tenacity
import concurrent.futures

# Initialize Stripe with API key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")


class StripeError(Exception):
    pass


class StripeService:
    def __init__(
        self, db: Session, settings: Optional[Union[Settings, Depends]] = None
    ):
        """
        Initialize StripeService.

        Args:
            db: Database session
            settings: Optional settings object or Depends object. If not provided, will try to get from environment.
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

    async def create_payment_intent(self, quote: Quote) -> Dict[str, Any]:
        """
        Create a Stripe PaymentIntent for a quote.

        Args:
            quote: The Quote object to create a payment for

        Returns:
            Dict containing client_secret and payment_intent_id
        """

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
            )

        try:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                intent = pool.submit(_create_intent_sync).result()
            # Create transaction record
            transaction = Transaction(
                quote_id=quote.id,
                provider=PaymentProvider.stripe,
                provider_id=intent.id,
                amount_usd=quote.price,
                status="pending",
            )
            self.db.add(transaction)
            self.db.commit()

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
            }
        except stripe.error.StripeError as e:
            print(f"Stripe error: {str(e)}")
            self.db.rollback()
            raise StripeError(str(e))
        except Exception as e:
            self.db.rollback()
            raise StripeError(str(e))

    async def handle_webhook_event(self, payload: bytes, sig_header: str) -> None:
        """
        Handle incoming Stripe webhook events.

        Args:
            payload: Raw request body bytes
            sig_header: Stripe signature header
        """
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

            # Handle payment_intent.succeeded event
            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object
                await self._handle_successful_payment(payment_intent)

            # Handle payment_intent.payment_failed event
            elif event.type == "payment_intent.payment_failed":
                payment_intent = event.data.object
                await self._handle_failed_payment(payment_intent)

        except stripe.error.SignatureVerificationError:
            print("Invalid signature")
            raise
        except Exception as e:
            print(f"Error handling webhook: {str(e)}")
            raise

    async def _handle_successful_payment(
        self, payment_intent: stripe.PaymentIntent
    ) -> None:
        """Update transaction and quote status for successful payment."""
        # Find associated transaction
        transaction = (
            self.db.query(Transaction).filter_by(provider_id=payment_intent.id).first()
        )

        if transaction:
            # Update transaction status
            transaction.status = "succeeded"

            # Update quote status to indicate payment
            quote = transaction.quote
            quote.status = "paid"

            self.db.commit()

    async def _handle_failed_payment(
        self, payment_intent: stripe.PaymentIntent
    ) -> None:
        """Update transaction status for failed payment."""
        transaction = (
            self.db.query(Transaction).filter_by(provider_id=payment_intent.id).first()
        )

        if transaction:
            transaction.status = "failed"
            self.db.commit()
