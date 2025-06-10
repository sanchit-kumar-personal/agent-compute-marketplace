"""
API Routes Module

This module defines FastAPI routes for:
- Resource discovery and management
- Negotiation endpoints
- Payment processing
- Transaction history
- System health and metrics
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Union
from sqlalchemy.orm import Session
from . import schemas
from db.session import get_db
from db.models import Quote, QuoteStatus
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from agents.seller import SellerAgent
from negotiation.engine import NegotiationEngine
import json

router = APIRouter()


def get_seller_agent():
    """FastAPI dependency for SellerAgent."""
    return SellerAgent()


# Resource routes
@router.get("/resources", response_model=List[schemas.ComputeResource])
async def list_resources():
    """List available compute resources."""
    pass


@router.get("/resources/{resource_id}", response_model=schemas.ComputeResource)
async def get_resource(resource_id: int):
    """Get details of a specific compute resource."""
    pass


# Negotiation routes
@router.post("/negotiations", response_model=schemas.Negotiation)
async def create_negotiation():
    """Start a new negotiation session."""
    pass


@router.get("/negotiations/{negotiation_id}", response_model=schemas.Negotiation)
async def get_negotiation(negotiation_id: int):
    """Get status of a specific negotiation."""
    pass


# Payment routes
@router.post("/payments", response_model=schemas.Transaction)
async def process_payment():
    """Process a payment for agreed terms."""
    pass


@router.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
async def get_transaction(transaction_id: int):
    """Get details of a specific transaction."""
    pass


class QuoteRequest(BaseModel):
    buyer_id: str
    resource_type: str
    duration_hours: int


class QuoteOut(BaseModel):
    id: int
    buyer_id: str
    resource_type: str
    duration_hours: int
    price: float  # Price is required
    status: str
    created_at: datetime
    negotiation_log: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)

    @field_validator("negotiation_log", mode="before")
    @classmethod
    def parse_negotiation_log(
        cls, value: Union[str, List, None]
    ) -> List[Dict[str, Any]]:
        """Parse negotiation_log from various input types into a list of dicts."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return []


@router.post("/quote-request", response_model=dict, status_code=201)
def create_quote(req: QuoteRequest, db: Session = Depends(get_db)):
    # Create quote with pending status - price will be set during negotiation
    quote_data = req.model_dump()
    quote = Quote(**quote_data, status=QuoteStatus.pending)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return {"quote_id": quote.id}


@router.get("/quote/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: int, db: Session = Depends(get_db)):
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


@router.post("/quote/{quote_id}/negotiate", response_model=QuoteOut)
async def negotiate_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    seller: SellerAgent = Depends(get_seller_agent),
):
    """Negotiate a quote price.

    Returns 409 if quote is already priced.
    Returns 404 if quote not found.
    """
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )

    if quote.status != QuoteStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Quote is not in pending status",
        )

    engine = NegotiationEngine(seller)
    try:
        updated = await engine.run_loop(db, quote_id)
        db.commit()
        return updated
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/quote/{quote_id}/negotiate/auto", response_model=QuoteOut)
async def auto_negotiate_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    seller: SellerAgent = Depends(get_seller_agent),
):
    """Run automated multi-turn negotiation for a quote.

    Returns:
        200: Successfully completed negotiation (accepted/rejected)
        404: Quote not found
        409: Quote already negotiated
        400: Invalid quote state or negotiation error
    """
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )

    if quote.status == QuoteStatus.pending:
        # First get initial quote
        engine = NegotiationEngine(seller)
        try:
            quote = await engine.run_loop(db, quote_id)
            db.commit()
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )

    if quote.status != QuoteStatus.priced:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Quote is not in priced status",
        )

    # Now start negotiation
    try:
        updated = await engine.negotiate(db, quote_id)
        db.commit()
        return updated
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
