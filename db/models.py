"""
Database Models Module

This module defines SQLAlchemy ORM models for:
- Compute resources
- Negotiations
- Transactions
- Payment records
- Audit logs
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import declarative_base
from datetime import datetime, UTC
from enum import Enum as PyEnum
from sqlalchemy.ext.hybrid import hybrid_property
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


class Transaction(Base):
    """Model representing completed transactions."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    negotiation_id = Column(Integer, ForeignKey("negotiations.id"))
    amount = Column(Float)
    payment_method = Column(String(20))  # e.g., "stripe", "paypal", "crypto"
    status = Column(String(20))  # e.g., "pending", "completed", "failed"
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class QuoteStatus(PyEnum):
    pending = "pending"
    priced = "priced"
    accepted = "accepted"
    rejected = "rejected"


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    duration_hours = Column(Integer, nullable=False)
    price = Column(Float, default=0.0)
    status = Column(Enum(QuoteStatus), default=QuoteStatus.pending)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    _negotiation_log = Column(
        "negotiation_log", Text, server_default="[]", nullable=False
    )

    @hybrid_property
    def negotiation_log(self) -> str:
        """Get the negotiation log as a JSON string."""
        return self._negotiation_log or "[]"

    @negotiation_log.setter
    def negotiation_log(self, value: str | List[Dict[str, Any]]) -> None:
        """Set the negotiation log from either a JSON string or list of dictionaries."""
        if isinstance(value, str):
            try:
                # Validate it's valid JSON
                json.loads(value)
                self._negotiation_log = value
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {str(e)}")
        else:
            try:
                self._negotiation_log = json.dumps(value)
            except TypeError as e:
                raise ValueError(f"Invalid negotiation log data: {str(e)}")

    def __repr__(self):
        return f"<Quote(id={self.id}, status={self.status})>"
