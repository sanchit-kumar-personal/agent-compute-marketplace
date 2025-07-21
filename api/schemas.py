"""
API Schemas Module

This module defines Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from db.models import PaymentProvider, QuoteStatus, TransactionStatus


class ComputeResource(BaseModel):
    """Schema for compute resources available in the marketplace."""

    id: int
    type: str  # e.g. "GPU", "CPU", "TPU"
    name: str  # e.g. "NVIDIA A100", "AMD EPYC"
    description: str
    price_per_hour: float
    available: bool

    model_config = ConfigDict(from_attributes=True)


class TransactionOut(BaseModel):
    id: int
    quote_id: int
    provider: PaymentProvider
    provider_id: str
    amount_usd: float
    status: TransactionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuoteBase(BaseModel):
    resource_type: str
    duration_hours: int
    buyer_max_price: float | None = 0.0


class QuoteCreate(QuoteBase):
    buyer_id: str


class QuoteOut(QuoteBase):
    id: int
    buyer_id: str
    price: float
    status: QuoteStatus
    created_at: datetime
    transactions: list[TransactionOut] | None = None
    negotiation_log: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)


class Negotiation(BaseModel):
    """Schema for negotiation sessions."""

    id: int
    quote_id: int
    status: str  # "pending", "accepted", "rejected"
    rounds: list[dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Transaction(BaseModel):
    """Schema for payment transactions."""

    id: int
    quote_id: int
    provider: PaymentProvider
    provider_id: str
    amount_usd: float
    status: TransactionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
