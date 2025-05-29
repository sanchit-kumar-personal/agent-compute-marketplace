"""
API Schemas Module

This module defines Pydantic models for:
- Request/response validation
- Data serialization
- API documentation
- Type checking
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict
from datetime import datetime


class ComputeResource(BaseModel):
    """Schema for compute resource data."""

    id: Optional[int] = None
    type: str
    specs: Dict[str, str]
    price_per_hour: float
    status: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Negotiation(BaseModel):
    """Schema for negotiation session data."""

    id: Optional[int] = None
    buyer_id: str
    seller_id: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Transaction(BaseModel):
    """Schema for transaction data."""

    id: Optional[int] = None
    negotiation_id: int
    amount: float
    payment_method: str
    status: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
