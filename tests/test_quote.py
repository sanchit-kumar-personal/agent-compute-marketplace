"""
Tests for the quote workflow functionality.
"""

import os
import pytest
from fastapi.testclient import TestClient
from main import app
from db.models import Base
from db.session import get_db
from core.dependencies import init_settings, clear_settings
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def test_db():
    """Create a test database session."""
    # Set up in-memory database
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    # Initialize settings
    init_settings()

    # Create engine with thread-safe settings for SQLite
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    Base.metadata.create_all(engine)

    # Create a session factory
    TestingSessionLocal = Session(bind=engine)

    # Override the get_db dependency
    def override_get_db():
        try:
            yield TestingSessionLocal
        finally:
            pass  # Session cleanup handled by fixture

    # Replace the dependency
    app.dependency_overrides[get_db] = override_get_db

    yield  # Run the tests

    # Cleanup
    TestingSessionLocal.close()
    engine.dispose()
    app.dependency_overrides.clear()
    clear_settings()
    if old_db_url:
        os.environ["DATABASE_URL"] = old_db_url


def test_quote_workflow(test_db):
    """Test the happy path of the quote workflow."""
    with TestClient(app) as client:
        # Create a quote request
        response = client.post(
            "/api/quote-request",
            json={"buyer_id": "alice", "resource_type": "GPU", "duration_hours": 4},
        )
        assert response.status_code == 201
        quote_id = response.json()["quote_id"]
        assert quote_id > 0

        # Get the quote details
        response = client.get(f"/api/quote/{quote_id}")
        assert response.status_code == 200
        quote = response.json()
        assert (
            quote["status"] == "priced"
        )  # Quote is created with price and priced status
        assert quote["duration_hours"] == 4
        assert quote["price"] == 6.0  # 1.50 * 4 hours from SellerAgent.generate_quote()
