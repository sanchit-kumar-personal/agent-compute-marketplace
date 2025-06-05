"""
API Routes Module

This module defines FastAPI routes for:
- Resource discovery and management
- Negotiation endpoints
- Payment processing
- Transaction history
- System health and metrics
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from . import schemas
from db.session import get_db
from db.models import Quote
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from agents.seller import SellerAgent
from db.models import QuoteStatus

router = APIRouter()

# Initialize seller agent for quote generation
seller_agent = SellerAgent()


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

    model_config = ConfigDict(from_attributes=True)


@router.post("/quote-request", response_model=dict, status_code=201)
def create_quote(req: QuoteRequest, db: Session = Depends(get_db)):
    # Calculate price using seller agent
    quote_data = req.model_dump()
    price = seller_agent.generate_quote(quote_data)

    # Create quote with calculated price and set status to priced
    quote = Quote(**quote_data, price=price, status=QuoteStatus.priced)
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
