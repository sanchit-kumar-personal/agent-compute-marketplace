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
from main import get_settings

router = APIRouter(prefix="/quotes")


@router.post("/request", status_code=201)
async def create_quote(quote_data: QuoteCreate, db: Session = Depends(get_db)):
    """
    Create a new quote request.
    """
    quote = Quote(
        buyer_id=quote_data.buyer_id,
        resource_type=quote_data.resource_type,
        duration_hours=quote_data.duration_hours,
        status=QuoteStatus.pending,
        created_at=datetime.now(UTC),
        negotiation_log=[],
    )

    db.add(quote)
    db.commit()
    db.refresh(quote)

    return {"quote_id": quote.id}


@router.get("/{quote_id}")
async def get_quote(quote_id: int, db: Session = Depends(get_db)):
    """
    Get quote details by ID.
    """
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    return quote


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

    return quote


@router.post("/{quote_id}/negotiate/auto")
async def auto_negotiate(quote_id: int, db: Session = Depends(get_db)):
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

    # Create payment after successful negotiation
    payment = await create_payment(quote, db)

    return {"status": quote.status, "transaction_id": payment.id}


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
    """Helper function to create a payment transaction."""
    stripe_service = StripeService(db=db, settings=settings)
    try:
        payment_intent_data = await stripe_service.create_payment_intent(quote)
    except StripeError as e:
        quote.status = QuoteStatus.rejected
        db.commit()
        raise HTTPException(status_code=402, detail=f"payment declined: {str(e)}")
    except Exception as e:
        quote.status = QuoteStatus.rejected
        db.commit()
        raise HTTPException(
            status_code=502, detail=f"payment service unavailable: {str(e)}"
        )
    transaction = Transaction(
        quote_id=quote.id,
        provider=PaymentProvider.stripe,
        provider_id=payment_intent_data["payment_intent_id"],
        amount_usd=quote.price,
        status=TransactionStatus.pending,
        created_at=datetime.now(UTC),
    )
    db.add(transaction)
    db.commit()
    return transaction
