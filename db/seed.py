"""
Database Seed Module

This module provides functionality to:
- Initialize the database with sample data
- Create test accounts and resources
- Generate synthetic transaction history
- Set up development environment
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, ComputeResource, Negotiation, Transaction

def init_db(database_url: str):
    """Initialize database and create tables."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine

def create_sample_data(engine):
    """Populate database with sample data for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Add sample compute resources
        sample_resources = [
            ComputeResource(
                type="GPU",
                specs='{"model": "NVIDIA A100", "memory": "80GB"}',
                price_per_hour=10.0,
                status="available"
            ),
            ComputeResource(
                type="CPU",
                specs='{"cores": 64, "memory": "256GB"}',
                price_per_hour=5.0,
                status="available"
            )
        ]
        session.add_all(sample_resources)
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    # For local development
    DATABASE_URL = "sqlite:///./test.db"
    engine = init_db(DATABASE_URL)
    create_sample_data(engine) 