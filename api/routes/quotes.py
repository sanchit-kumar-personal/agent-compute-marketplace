"""
Quote management routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import (
    Quote,
    Transaction,
    QuoteStatus,
    PaymentProvider,
    TransactionStatus,
)
from api.schemas import QuoteCreate, QuoteOut
from payments.stripe_service import StripeService, StripeError
from datetime import datetime, UTC
from core.settings import Settings
from core.dependencies import get_settings
import logging
from typing import List
import structlog
from core.logging import BusinessEvents
from core.metrics import quotes_total

logger = logging.getLogger(__name__)
log = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/request", status_code=201)
async def create_quote(quote_data: QuoteCreate, db: Session = Depends(get_db)):
    """
    Create a new quote request.
    """
    quote = Quote(
        buyer_id=quote_data.buyer_id,
        resource_type=quote_data.resource_type,
        duration_hours=quote_data.duration_hours,
        buyer_max_price=quote_data.buyer_max_price,
        status=QuoteStatus.pending,
        created_at=datetime.now(UTC),
        negotiation_log=[],
    )

    db.add(quote)
    db.commit()
    db.refresh(quote)

    # Increment Prometheus counter
    quotes_total.inc()

    log.info(
        BusinessEvents.QUOTE_CREATED,
        quote_id=quote.id,
        buyer_id=quote.buyer_id,
        resource_type=quote.resource_type,
        duration_hours=quote.duration_hours,
        buyer_max_price=quote.buyer_max_price,
    )

    return {"quote_id": quote.id}


@router.get("/recent", response_model=List[QuoteOut])
async def recent_quotes(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent quotes ordered by creation date."""
    quotes = db.query(Quote).order_by(Quote.created_at.desc()).limit(limit).all()

    # Convert to QuoteOut models which will handle enum serialization
    return [
        QuoteOut(
            id=q.id,
            buyer_id=q.buyer_id,
            resource_type=q.resource_type,
            duration_hours=q.duration_hours,
            price=float(q.price) if q.price is not None else 0.0,
            buyer_max_price=(
                float(q.buyer_max_price) if q.buyer_max_price is not None else 0.0
            ),
            status=q.status,  # This is already a QuoteStatus enum
            created_at=q.created_at,
            negotiation_log=q.negotiation_log,
            transactions=(
                [
                    {
                        "id": tx.id,
                        "quote_id": tx.quote_id,
                        "provider": tx.provider,  # This is already a PaymentProvider enum
                        "provider_id": tx.provider_id,
                        "amount_usd": float(tx.amount_usd),
                        "status": tx.status,  # This is already a TransactionStatus enum
                        "created_at": tx.created_at,
                    }
                    for tx in q.transactions
                ]
                if q.transactions
                else None
            ),
        )
        for q in quotes
    ]


@router.get("/{quote_id}")
async def get_quote(quote_id: int, db: Session = Depends(get_db)):
    """
    Get quote details by ID.
    """
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Convert to dict and include transactions
    return {
        "id": quote.id,
        "buyer_id": quote.buyer_id,
        "resource_type": quote.resource_type,
        "duration_hours": quote.duration_hours,
        "price": quote.price,
        "buyer_max_price": quote.buyer_max_price,
        "status": quote.status.value,
        "created_at": quote.created_at,
        "negotiation_log": quote.negotiation_log,
        "transactions": [
            {
                "id": tx.id,
                "quote_id": tx.quote_id,
                "provider": tx.provider.value,
                "provider_id": tx.provider_id,
                "amount_usd": float(tx.amount_usd),
                "status": tx.status.value,
                "created_at": tx.created_at,
            }
            for tx in quote.transactions
        ],
    }


@router.post("/{quote_id}/negotiate", response_model=QuoteOut)
async def negotiate_quote(quote_id: int, db: Session = Depends(get_db)):
    """
    Negotiate a quote - simple implementation that sets a fixed price based on resource type and duration.
    """
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != QuoteStatus.pending:
        raise HTTPException(status_code=409, detail="Quote is not in pending status")

    # Simple pricing logic - in reality this would be more complex
    base_price = 2.0 if quote.resource_type == "GPU" else 1.0
    quote.price = base_price * quote.duration_hours
    quote.status = QuoteStatus.priced

    # Add negotiation log entry
    log_entry = {
        "role": "seller",
        "price": quote.price,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    current_log = quote.negotiation_log
    current_log.append(log_entry)
    quote.negotiation_log = current_log

    db.commit()
    db.refresh(quote)

    # Log negotiation turn
    log.info(
        BusinessEvents.NEGOTIATION_TURN,
        quote_id=quote.id,
        current_price=quote.price,
        status=quote.status.value,
        turn_number=len(quote.negotiation_log),
    )

    # Log quote status change
    if quote.status == QuoteStatus.priced:
        log.info(
            BusinessEvents.QUOTE_ACCEPTED, quote_id=quote.id, final_price=quote.price
        )

    return quote


@router.post("/{quote_id}/negotiate/auto", response_model=QuoteOut)
async def auto_negotiate(
    quote_id: int,
    provider: str = "stripe",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Auto-negotiate a quote and create payment intent.
    Only works for pending quotes.
    """
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Only allow auto-negotiation for pending quotes
    if quote.status != QuoteStatus.pending:
        raise HTTPException(
            status_code=409,
            detail=f"Quote {quote_id} is not in pending status",
        )

    # Run auto-negotiation
    quote.status = QuoteStatus.accepted
    quote.price = 100.0  # Mock price for testing
    db.add(quote)
    db.commit()

    if provider == "paypal":
        from payments.paypal_service import PayPalService, PayPalError

        try:
            paypal = PayPalService()
            capture_result = paypal.create_and_capture(quote.price, quote.id)

            # Log PayPal capture result
            logger.info(
                "paypal capture %s %s",
                capture_result["status"],
                capture_result["capture_id"],
            )

            # Create transaction record
            tx = Transaction(
                quote_id=quote.id,
                provider=PaymentProvider.paypal,
                provider_id=capture_result["capture_id"],
                amount_usd=quote.price,
                status=PayPalService.map_status(capture_result["status"]),
                created_at=datetime.now(UTC),
            )
            db.add(tx)

            # Only update to paid if transaction succeeded
            if tx.status == TransactionStatus.succeeded:
                quote.status = QuoteStatus.paid
            else:
                # Mark as rejected and raise 402 for declined payments
                quote.status = QuoteStatus.rejected
                db.commit()
                raise HTTPException(status_code=402, detail="paypal capture declined")

            db.commit()
            db.refresh(quote)  # Refresh to get the updated quote with transactions

            # Log negotiation turn
            log.info(
                BusinessEvents.NEGOTIATION_TURN,
                quote_id=quote.id,
                current_price=quote.price,
                status=quote.status,
                turn_number=len(quote.negotiation_log) if quote.negotiation_log else 0,
            )

            if quote.status == QuoteStatus.accepted:
                log.info(
                    BusinessEvents.QUOTE_ACCEPTED,
                    quote_id=quote.id,
                    final_price=quote.price,
                )
            elif quote.status == QuoteStatus.rejected:
                log.info(
                    BusinessEvents.QUOTE_REJECTED,
                    quote_id=quote.id,
                    reason="negotiation_failed",
                )

            return quote

        except PayPalError:
            # Keep as accepted if payment failed - allows retrying
            db.commit()
            raise HTTPException(status_code=502, detail="paypal unavailable")
    else:
        try:
            # Create Stripe payment
            payment = await create_payment(quote, db, settings)
            if payment.status == TransactionStatus.succeeded:
                quote.status = QuoteStatus.paid
            else:
                # Keep as accepted if payment failed - allows retrying
                quote.status = QuoteStatus.accepted
            db.commit()
            db.refresh(quote)  # Refresh to get the updated quote with transactions

            # Log negotiation turn
            log.info(
                BusinessEvents.NEGOTIATION_TURN,
                quote_id=quote.id,
                current_price=quote.price,
                status=quote.status,
                turn_number=len(quote.negotiation_log) if quote.negotiation_log else 0,
            )

            if quote.status == QuoteStatus.accepted:
                log.info(
                    BusinessEvents.QUOTE_ACCEPTED,
                    quote_id=quote.id,
                    final_price=quote.price,
                )
            elif quote.status == QuoteStatus.rejected:
                log.info(
                    BusinessEvents.QUOTE_REJECTED,
                    quote_id=quote.id,
                    reason="negotiation_failed",
                )

            return quote
        except StripeError:
            # Keep as accepted if payment failed - allows retrying
            db.commit()
            raise HTTPException(status_code=502, detail="stripe unavailable")


@router.post("/{quote_id}/payments")
async def create_quote_payment(quote_id: int, db: Session = Depends(get_db)):
    """
    Create a payment for an accepted quote.
    """
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != QuoteStatus.accepted:
        raise HTTPException(
            status_code=409,
            detail=f"Quote {quote_id} must be in accepted status to create payment",
        )

    # Check if transaction already exists
    existing_transaction = db.query(Transaction).filter_by(quote_id=quote.id).first()
    if existing_transaction:
        raise HTTPException(
            status_code=409,
            detail=f"Quote {quote_id} already has a payment transaction",
        )

    payment = await create_payment(quote, db)
    return {"transaction_id": payment.id}


async def create_payment(
    quote: Quote, db: Session, settings: Settings = Depends(get_settings)
) -> Transaction:
    """Helper function to create a payment transaction.

    Creates a Stripe PaymentIntent and returns the transaction record created
    by the StripeService. The transaction starts in pending status and will
    be updated to succeeded/failed when Stripe sends the webhook notification.
    """
    stripe_service = StripeService(db=db, settings=settings)
    try:
        payment_intent_data = await stripe_service.create_payment_intent(quote)
        # Get the transaction that was created by StripeService
        transaction = (
            db.query(Transaction)
            .filter_by(provider_id=payment_intent_data["payment_intent_id"])
            .first()
        )
        if not transaction:
            raise ValueError("Transaction not found after creating payment intent")
        return transaction
    except StripeError as e:
        quote.status = QuoteStatus.accepted  # Keep as accepted to allow retry
        db.commit()
        raise HTTPException(status_code=402, detail=f"payment declined: {str(e)}")
    except Exception as e:
        quote.status = QuoteStatus.accepted  # Keep as accepted to allow retry
        db.commit()
        raise HTTPException(
            status_code=502, detail=f"payment service unavailable: {str(e)}"
        )
