"""
Database Models Module

This module defines SQLAlchemy ORM models for:
- Compute resources
- Negotiations
- Transactions
- Payment records
- Audit logs
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    Numeric,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, UTC
from enum import Enum as PyEnum
from typing import List, Dict, Any
import json

Base = declarative_base()


class ComputeResource(Base):
    """Model representing available compute resources."""

    __tablename__ = "compute_resources"

    id = Column(Integer, primary_key=True)
    type = Column(String(50))  # e.g., "GPU", "CPU"
    specs = Column(String(255))  # JSON string of specifications
    price_per_hour = Column(Float)
    status = Column(String(20))  # e.g., "available", "reserved"
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class Negotiation(Base):
    """Model representing negotiation sessions."""

    __tablename__ = "negotiations"

    id = Column(Integer, primary_key=True)
    buyer_id = Column(String(50))
    seller_id = Column(String(50))
    status = Column(String(20))  # e.g., "active", "completed", "failed"
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class PaymentProvider(PyEnum):
    stripe = "stripe"
    paypal = "paypal"


class TransactionStatus(PyEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class Transaction(Base):
    """Model representing payment transactions."""

    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_quote_status", "quote_id", "status"),)

    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    provider = Column(Enum(PaymentProvider), nullable=False)
    provider_id = Column(String(255), nullable=False)
    amount_usd = Column(Numeric(10, 2), nullable=False)
    status = Column(
        Enum(TransactionStatus), nullable=False, default=TransactionStatus.pending
    )
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<Transaction(id={self.id}, quote_id={self.quote_id}, status={self.status})>"


class QuoteStatus(PyEnum):
    pending = "pending"
    priced = "priced"
    accepted = "accepted"
    rejected = "rejected"
    countered = "countered"
    paid = "paid"


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    duration_hours = Column(Integer, nullable=False)
    price = Column(Float, default=0.0)
    buyer_max_price = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(QuoteStatus), default=QuoteStatus.pending)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    _negotiation_log = Column("negotiation_log", Text, nullable=False, default="[]")

    # Add relationship to transactions
    transactions = relationship("Transaction", backref="quote", lazy="dynamic")

    @property
    def negotiation_log(self) -> List[Dict[str, Any]]:
        """Get the negotiation log as a list of dictionaries."""
        if not self._negotiation_log:
            return []
        try:
            return json.loads(self._negotiation_log)
        except (json.JSONDecodeError, TypeError):
            return []

    @negotiation_log.setter
    def negotiation_log(self, value: List[Dict[str, Any]]) -> None:
        """Set the negotiation log, converting to JSON string if needed."""
        if isinstance(value, str):
            # Validate it's a valid JSON string
            try:
                json.loads(value)
                self._negotiation_log = value
            except json.JSONDecodeError:
                self._negotiation_log = "[]"
        else:
            # Convert list to JSON string
            try:
                self._negotiation_log = json.dumps(value)
            except (TypeError, ValueError):
                self._negotiation_log = "[]"

    def __repr__(self):
        return f"<Quote(id={self.id}, status={self.status})>"
