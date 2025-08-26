"""
Quote management routes with enhanced negotiation and market features
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import QuoteCreate, QuoteOut, PaymentResponse
from agents.negotiation_engine import NegotiationEngine
from core.dependencies import get_settings
from core.logging import BusinessEvents
from core.metrics import quotes_total
from core.settings import Settings
from db.models import (
    PaymentProvider,
    Quote,
    QuoteStatus,
    Transaction,
    TransactionStatus,
    AuditLog,
    AuditAction,
    ComputeResource,
    Reservation,
)
from db.session import get_async_db
from payments.stripe_service import StripeError, StripeService
from payments.paypal_service import PayPalService, PayPalError
from decimal import Decimal

logger = logging.getLogger(__name__)
log = structlog.get_logger(__name__)

router = APIRouter()

# Global negotiation engine instance
negotiation_engine = NegotiationEngine()


async def create_reservation(db: AsyncSession, quote: Quote) -> Reservation:
    """Create a reservation after successful payment (idempotent)."""
    # Check if a reservation already exists for this quote
    result = await db.execute(
        select(Reservation).filter(Reservation.quote_id == quote.id)
    )
    existing_reservation = result.scalars().first()
    if existing_reservation:
        return existing_reservation

    # Find an available compute resource of the requested type (best-effort)
    compute_result = await db.execute(
        select(ComputeResource).filter(
            ComputeResource.type == quote.resource_type,
            ComputeResource.status == "available",
        )
    )
    compute_resource = compute_result.scalars().first()

    if not compute_resource:
        raise ValueError(f"No available {quote.resource_type} resources")

    # Create reservation matching the model schema
    reservation = Reservation(
        quote_id=quote.id,
        resource_type=quote.resource_type,
        quantity=1,
        duration_hours=quote.duration_hours,
        expires_at=datetime.now(UTC) + timedelta(hours=quote.duration_hours),
        status="active",
    )
    db.add(reservation)

    # Mark one unit as reserved in inventory model for realism
    compute_resource.status = "reserved"

    return reservation


@router.post("/request", status_code=201)
async def create_quote(
    quote_data: QuoteCreate, db: AsyncSession = Depends(get_async_db)
):
    """
    Create a new quote request with enhanced validation and market awareness.

    This is the starting point for all compute resource procurement. The quote will be
    initially set to `pending` status and can then be processed through AI negotiation.

    **Request Example:**
    ```json
    {
        "buyer_id": "user_123",
        "resource_type": "GPU",
        "duration_hours": 24,
        "buyer_max_price": 100.0
    }
    ```

    **Response Example:**
    ```json
    {
        "quote_id": 42,
        "status": "pending",
        "message": "Quote request created successfully"
    }
    ```

    **Next Steps:**
    - Use `/negotiate` for AI-powered pricing
    - Use `/negotiate/auto` for end-to-end negotiation + payment
    - Use `/negotiate/multi-turn` for sophisticated agent negotiations
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

    # Snapshot fields needed for audit/logging before commit to avoid
    # attribute expiration refreshes under concurrent load
    buyer_id_snapshot = quote.buyer_id
    resource_type_snapshot = quote.resource_type
    duration_snapshot = quote.duration_hours
    buyer_max_price_snapshot = float(quote.buyer_max_price)

    # Persist using thread-safe path under SQLite adapter
    if hasattr(db, "sync_session"):
        # Use the underlying sync session to avoid thread switching on SQLite
        db.sync_session.add(quote)
        db.sync_session.commit()
    else:
        db.add(quote)
        await db.commit()

    # Increment Prometheus counter
    quotes_total.inc()

    # Add audit log (best-effort; don't fail request if audit insert fails)
    try:
        audit_log = AuditLog(
            quote_id=quote.id,
            action=AuditAction.quote_created,
            payload={
                "buyer_id": buyer_id_snapshot,
                "resource_type": resource_type_snapshot,
                "duration_hours": duration_snapshot,
                "buyer_max_price": buyer_max_price_snapshot,
            },
        )
        if hasattr(db, "sync_session"):
            db.sync_session.add(audit_log)
            db.sync_session.commit()
        else:
            db.add(audit_log)
            await db.commit()
    except Exception as e:  # pragma: no cover
        log.warning("audit.insert_failed", error=str(e))
        try:
            if hasattr(db, "sync_session"):
                db.sync_session.rollback()
            else:
                await db.rollback()
        except Exception:
            pass

    log.info(
        BusinessEvents.QUOTE_CREATED,
        quote_id=quote.id,
        buyer_id=buyer_id_snapshot,
        resource_type=resource_type_snapshot,
        duration_hours=duration_snapshot,
        buyer_max_price=buyer_max_price_snapshot,
    )

    return {
        "quote_id": quote.id,
        "status": "pending",
        "message": "Quote request created successfully",
    }


@router.get("/recent")
async def get_recent_quotes(
    limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_async_db)
):
    """
    Get recent quotes with enhanced details for dashboard display.
    """
    result = await db.execute(
        select(Quote).order_by(desc(Quote.created_at)).limit(limit)
    )
    quotes = result.scalars().all()

    result = []
    for quote in quotes:
        # Get related transactions
        tx_result = await db.execute(
            select(Transaction).filter(Transaction.quote_id == quote.id)
        )
        transactions = tx_result.scalars().all()

        quote_dict = {
            "id": quote.id,
            "buyer_id": quote.buyer_id,
            "resource_type": quote.resource_type,
            "duration_hours": quote.duration_hours,
            "buyer_max_price": quote.buyer_max_price,
            "price": quote.price,
            "status": quote.status.value,
            "created_at": quote.created_at,
            "negotiation_log": quote.negotiation_log or [],
            "transactions": [
                {
                    "id": tx.id,
                    "quote_id": tx.quote_id,
                    "provider": tx.provider.value,
                    "amount_usd": tx.amount_usd,
                    "status": tx.status.value,
                    "provider_id": tx.provider_id,
                    "created_at": tx.created_at,
                }
                for tx in transactions
            ],
        }
        result.append(quote_dict)

    return result


@router.get("/{quote_id}", response_model=QuoteOut)
async def get_quote(quote_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Get quote details with enhanced information including negotiation history.
    """
    result = await db.execute(select(Quote).filter(Quote.id == quote_id))
    quote = result.scalars().first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Get negotiation session info if available
    negotiation_session = negotiation_engine.get_negotiation_session(quote_id)

    # Get related transactions
    tx_result = await db.execute(
        select(Transaction).filter(Transaction.quote_id == quote_id)
    )
    transactions = tx_result.scalars().all()

    # Build enhanced response
    quote_dict = {
        "id": quote.id,
        "buyer_id": quote.buyer_id,
        "resource_type": quote.resource_type,
        "duration_hours": quote.duration_hours,
        "buyer_max_price": quote.buyer_max_price,
        "price": quote.price,
        "status": quote.status.value,
        "created_at": quote.created_at,
        "negotiation_log": quote.negotiation_log or [],
        "transactions": [
            {
                "id": tx.id,
                "quote_id": tx.quote_id,  # Add missing quote_id field
                "provider": tx.provider.value,
                "amount_usd": tx.amount_usd,
                "status": tx.status.value,
                "provider_id": tx.provider_id,
                "created_at": tx.created_at,
            }
            for tx in transactions
        ],
        "negotiation_session": (
            {
                "state": negotiation_session.state if negotiation_session else "none",
                "round_number": (
                    negotiation_session.round_number if negotiation_session else 0
                ),
                "last_offer": (
                    negotiation_session.last_offer if negotiation_session else None
                ),
            }
            if negotiation_session
            else None
        ),
    }

    return quote_dict


@router.get("/", response_model=List[QuoteOut])
async def list_quotes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    buyer_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List quotes with advanced filtering and pagination.
    """
    stmt = select(Quote).order_by(desc(Quote.created_at))

    # Apply filters
    if status:
        try:
            status_enum = QuoteStatus(status)
            stmt = stmt.filter(Quote.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if buyer_id:
        stmt = stmt.filter(Quote.buyer_id == buyer_id)

    if resource_type:
        stmt = stmt.filter(Quote.resource_type == resource_type)

    # Apply pagination
    result = await db.execute(stmt.offset(skip).limit(limit))
    quotes = result.scalars().all()

    # Convert to response format
    result = []
    for quote in quotes:
        tx_result = await db.execute(
            select(Transaction).filter(Transaction.quote_id == quote.id)
        )
        transactions = tx_result.scalars().all()

        quote_dict = {
            "id": quote.id,
            "buyer_id": quote.buyer_id,
            "resource_type": quote.resource_type,
            "duration_hours": quote.duration_hours,
            "buyer_max_price": quote.buyer_max_price,
            "price": quote.price,
            "status": quote.status.value,
            "created_at": quote.created_at,
            "negotiation_log": quote.negotiation_log or [],
            "transactions": [
                {
                    "id": tx.id,
                    "quote_id": tx.quote_id,  # Add missing quote_id field
                    "provider": tx.provider.value,
                    "amount_usd": tx.amount_usd,
                    "status": tx.status.value,
                    "provider_id": tx.provider_id,
                    "created_at": tx.created_at,
                }
                for tx in transactions
            ],
        }
        result.append(quote_dict)

    return result


@router.post("/{quote_id}/negotiate", response_model=QuoteOut)
async def negotiate_quote(quote_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Start initial pricing for a quote (first step of negotiation).
    """
    result = await db.execute(select(Quote).filter(Quote.id == quote_id))
    quote = result.scalars().first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != QuoteStatus.pending:
        raise HTTPException(
            status_code=409,
            detail=f"Quote not in pending status, currently {quote.status.value}",
        )

    try:
        # Run the initial pricing loop
        updated_quote = await negotiation_engine.run_loop(db, quote_id)
        return updated_quote

    except Exception as e:
        log.error("negotiation.failed", quote_id=quote_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Negotiation failed: {str(e)}")


@router.post("/{quote_id}/negotiate/multi-turn", response_model=QuoteOut)
async def run_multi_turn_negotiation(
    quote_id: int,
    max_turns: int = Query(4, ge=1, le=10),
    urgency: float = Query(0.7, ge=0.0, le=1.0, description="Buyer urgency (0-1)"),
    strategy: str = Query(
        "balanced",
        pattern="^(aggressive|balanced|conservative)$",
        description="Buyer negotiation strategy",
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Run sophisticated multi-turn negotiation between AI agents.
    """
    result = await db.execute(select(Quote).filter(Quote.id == quote_id))
    quote = result.scalars().first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Quote must be priced first
    if quote.status not in [QuoteStatus.priced]:
        raise HTTPException(
            status_code=409,
            detail=f"Quote must be priced first. Current status: {quote.status.value}. Use /negotiate first.",
        )

    try:
        # Run multi-turn negotiation with specified parameters
        updated_quote = await negotiation_engine.negotiate(
            db, quote_id, max_turns=max_turns, urgency=urgency, strategy=strategy
        )
        return updated_quote

    except Exception as e:
        log.error("multi_turn_negotiation.failed", quote_id=quote_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Multi-turn negotiation failed: {str(e)}"
        )


@router.post("/{quote_id}/negotiate/auto", response_model=QuoteOut)
async def auto_negotiate_quote(
    quote_id: int,
    provider: str = Query(
        "stripe",
        pattern="^(stripe|paypal)$",
        description="Payment provider (stripe or paypal)",
    ),
    db: AsyncSession = Depends(get_async_db),
    settings: Settings = Depends(get_settings),
):
    """
    Complete end-to-end workflow: AI negotiation + payment processing.

    This endpoint provides a streamlined experience that combines:
    1. **AI-powered negotiation** between buyer and seller agents
    2. **Automatic payment processing** via Stripe or PayPal
    3. **Real-time market analysis** and pricing optimization

    **Workflow:**
    - If quote is `pending` → Run initial pricing negotiation
    - If quote is `priced` → Execute multi-turn agent negotiation
    - If negotiation reaches `accepted` → Process payment immediately
    - Return final quote with payment details

    **Payment Providers:**
    - `stripe`: Creates PaymentIntent for secure card processing
    - `paypal`: Creates and captures invoice (MVP: marks as paid immediately)

    **Use Cases:**
    - One-click quote-to-payment for web applications
    - Automated procurement workflows
    - Demo and testing environments
    """
    result = await db.execute(select(Quote).filter(Quote.id == quote_id))
    quote = result.scalars().first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Check if quote is in a state that allows auto-negotiation
    if quote.status not in [QuoteStatus.pending, QuoteStatus.priced]:
        raise HTTPException(
            status_code=409,
            detail=f"Quote not in pending status, currently {quote.status.value}",
        )

    try:
        # If quote is still pending, run initial pricing
        if quote.status == QuoteStatus.pending:
            quote = await negotiation_engine.run_loop(db, quote_id)

        # Run multi-turn negotiation with fixed parameters for auto mode
        if quote.status == QuoteStatus.priced:
            quote = await negotiation_engine.negotiate(
                db, quote_id, max_turns=3, urgency=0.7, strategy="balanced"
            )

        # Handle payment processing after successful negotiation
        if quote.status == QuoteStatus.accepted:
            log.info(
                "payment.attempt",
                quote_id=quote_id,
                amount=quote.price,
                provider=provider,
            )

            try:
                provider_enum = PaymentProvider(provider)

                if provider_enum == PaymentProvider.stripe:
                    stripe_service = StripeService(db, settings)

                    # Create payment intent
                    payment_intent = await stripe_service.create_payment_intent(quote)

                    # Create transaction record
                    transaction = Transaction(
                        quote_id=quote_id,
                        provider=provider_enum,
                        amount_usd=quote.price,
                        status=TransactionStatus.succeeded,
                        provider_id=payment_intent["payment_intent_id"],
                    )
                    db.add(transaction)

                    # Update quote status to paid and create reservation
                    quote.status = QuoteStatus.paid
                    await create_reservation(db, quote)
                    await db.commit()

                    log.info(
                        "payment.success",
                        quote_id=quote_id,
                        provider=provider,
                        transaction_id=transaction.id,
                    )

                elif provider_enum == PaymentProvider.paypal:
                    paypal_service = PayPalService()

                    # Create and immediately capture PayPal payment
                    payment_result = paypal_service.create_and_capture(
                        amount=Decimal(str(quote.price)), quote_id=quote_id
                    )

                    # Create transaction record
                    transaction = Transaction(
                        quote_id=quote_id,
                        provider=provider_enum,
                        amount_usd=quote.price,
                        status=TransactionStatus.succeeded,
                        provider_id=payment_result["id"],
                    )
                    db.add(transaction)

                    # Update quote status to paid and create reservation
                    quote.status = QuoteStatus.paid
                    await create_reservation(db, quote)
                    await db.commit()

                    log.info(
                        "payment.success",
                        quote_id=quote_id,
                        provider=provider,
                        transaction_id=transaction.id,
                    )

            except Exception as e:
                log.error(
                    "payment.failed", quote_id=quote_id, provider=provider, error=str(e)
                )
                # Keep quote as accepted even if payment fails
                pass

        return quote

    except (StripeError, PayPalError) as e:
        log.error("payment.failed", quote_id=quote_id, provider=provider, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Payment processing failed: {str(e)}"
        )
    except Exception as e:
        log.error("auto_negotiation.failed", quote_id=quote_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Auto-negotiation failed: {str(e)}"
        )


# TEMPORARILY DISABLED PAYMENT ENDPOINTS FOR DEBUGGING
# @router.post("/{quote_id}/payments", response_model=PaymentResponse)
# async def create_payment_intent(
#     quote_id: int,
#     provider: str = Query("stripe", pattern="^(stripe|paypal)$"),
#     db: Session = Depends(get_db),
#     settings: Settings = Depends(get_settings),
# ):
#     """Create a payment intent for an accepted quote."""
#     quote = db.query(Quote).filter(Quote.id == quote_id).first()
#     if not quote:
#         raise HTTPException(status_code=404, detail="Quote not found")
#
#     if quote.status != QuoteStatus.accepted:
#         raise HTTPException(status_code=400, detail="Quote must be accepted")
#
#     provider_enum = PaymentProvider(provider)
#
#     if provider_enum == PaymentProvider.stripe:
#         stripe_service = StripeService(db, settings)
#         payment_intent = await stripe_service.create_payment_intent(quote)
#
#         transaction = Transaction(
#             quote_id=quote_id,
#             provider=provider_enum,
#             amount_usd=quote.price,
#             status=TransactionStatus.pending,
#             provider_id=payment_intent["payment_intent_id"],
#         )
#         db.add(transaction)
#         db.commit()
#
#         return PaymentResponse(
#             provider=provider,
#             amount=quote.price,
#             transaction_id=transaction.id,
#             client_secret=payment_intent["client_secret"],
#             payment_intent_id=payment_intent["payment_intent_id"],
#             status="pending",
#         )
#
#     else:  # PayPal
#         paypal_service = PayPalService()
#         payment_result = paypal_service.create_and_capture(
#             amount=Decimal(str(quote.price)), quote_id=quote_id
#         )
#
#         transaction = Transaction(
#             quote_id=quote_id,
#             provider=provider_enum,
#             amount_usd=quote.price,
#             status=TransactionStatus.succeeded,
#             provider_id=payment_result["id"],
#         )
#         db.add(transaction)
#         quote.status = QuoteStatus.paid
#         db.commit()
#
#         return PaymentResponse(
#             provider=provider,
#             amount=quote.price,
#             transaction_id=transaction.id,
#             status="completed",
#             capture_id=payment_result["id"],
#         )


@router.post("/{quote_id}/payments", response_model=PaymentResponse)
async def create_payment_intent(
    quote_id: int,
    provider: str = Query("stripe", pattern="^(stripe|paypal)$"),
    db: AsyncSession = Depends(get_async_db),
    settings: Settings = Depends(get_settings),
):
    """Create a payment intent for an accepted quote."""
    result = await db.execute(select(Quote).filter(Quote.id == quote_id))
    quote = result.scalars().first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Check for existing payment transactions to prevent duplicates FIRST
    tx_existing = await db.execute(
        select(Transaction).filter(Transaction.quote_id == quote_id)
    )
    existing_transaction = tx_existing.scalars().first()
    if existing_transaction:
        raise HTTPException(
            status_code=409, detail="Quote already has a payment transaction"
        )

    if quote.status != QuoteStatus.accepted:
        raise HTTPException(status_code=400, detail="Quote must be accepted")

    provider_enum = PaymentProvider(provider)

    if provider_enum == PaymentProvider.stripe:
        try:
            stripe_service = StripeService(db, settings)
            payment_intent = await stripe_service.create_payment_intent(quote)

            # For demo purposes: mark transaction as succeeded immediately
            transaction = Transaction(
                quote_id=quote_id,
                provider=provider_enum,
                amount_usd=quote.price,
                status=TransactionStatus.succeeded,  # Demo: mark as succeeded immediately
                provider_id=payment_intent["payment_intent_id"],
            )
            db.add(transaction)

            # For demo purposes: mark quote as paid immediately and create reservation
            quote.status = QuoteStatus.paid
            await create_reservation(db, quote)
            await db.commit()

            return PaymentResponse(
                provider=provider,
                amount=quote.price,
                transaction_id=transaction.id,
                client_secret=payment_intent["client_secret"],
                payment_intent_id=payment_intent["payment_intent_id"],
                status="completed",  # Demo: return completed status
            )
        except StripeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    else:  # PayPal
        paypal_service = PayPalService()
        payment_result = paypal_service.create_and_capture(
            amount=Decimal(str(quote.price)), quote_id=quote_id
        )

        transaction = Transaction(
            quote_id=quote_id,
            provider=provider_enum,
            amount_usd=quote.price,
            status=TransactionStatus.succeeded,
            provider_id=payment_result["capture_id"],
        )
        db.add(transaction)
        quote.status = QuoteStatus.paid
        await create_reservation(db, quote)
        await db.commit()

        return PaymentResponse(
            provider=provider,
            amount=quote.price,
            transaction_id=transaction.id,
            status="completed",
            capture_id=payment_result["capture_id"],
        )
