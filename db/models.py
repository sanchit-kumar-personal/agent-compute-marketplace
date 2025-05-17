"""
Database Models Module

This module defines SQLAlchemy ORM models for:
- Compute resources
- Negotiations
- Transactions
- Payment records
- Audit logs
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, UTC

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
