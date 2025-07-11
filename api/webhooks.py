"""
Webhook handlers for payment providers
"""

import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db.models import (
    QuoteStatus,
    Transaction,
    TransactionStatus,
)
from db.session import get_db

router = APIRouter()

webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    # Get the signature from headers
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="signature missing")

    try:
        # Get the raw body
        payload = await request.body()

        # Verify webhook signature
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)

        # Handle payment_intent.succeeded
        if event.type == "payment_intent.succeeded":
            payment_intent = event.data.object

            # Find and update transaction
            transaction = (
                db.query(Transaction).filter_by(provider_id=payment_intent.id).first()
            )

            if transaction:
                # Update transaction and quote status
                transaction.status = TransactionStatus.succeeded
                quote = transaction.quote
                quote.status = QuoteStatus.paid
                db.commit()
                return {"status": "success"}
            else:
                raise HTTPException(status_code=404, detail="Transaction not found")

        # Handle payment_intent.payment_failed
        if event.type == "payment_intent.payment_failed":
            payment_intent = event.data.object
            transaction = (
                db.query(Transaction).filter_by(provider_id=payment_intent.id).first()
            )
            if transaction:
                transaction.status = TransactionStatus.failed
                quote = transaction.quote
                quote.status = QuoteStatus.rejected
                db.commit()
                return {"status": "failed"}
            else:
                raise HTTPException(status_code=404, detail="Transaction not found")

        return {"status": "success"}

    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
