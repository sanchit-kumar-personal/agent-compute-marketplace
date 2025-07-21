"""
Tests for the quote workflow functionality.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from core.dependencies import clear_settings, init_settings
from db.models import Base
from db.session import get_db
from main import app


# Unit tests using SQLite
@pytest.mark.unit
def test_quote_workflow(client):
    """Test the happy path of the quote workflow."""
    # Create a quote request
    response = client.post(
        "/quotes/request",
        json={
            "buyer_id": "alice",
            "resource_type": "GPU",
            "duration_hours": 4,
            "buyer_max_price": 10.0,  # Add required field
        },
    )
    assert response.status_code == 201
    quote_id = response.json()["quote_id"]
    assert quote_id > 0

    # Get the quote details - should be pending initially
    response = client.get(f"/quotes/{quote_id}")
    assert response.status_code == 200
    quote = response.json()
    assert quote["status"] == "pending"  # Quote starts in pending state
    assert quote["duration_hours"] == 4
    assert quote["price"] == 0.0  # No price set yet

    # Negotiate the quote
    response = client.post(f"/quotes/{quote_id}/negotiate")
    assert response.status_code == 200
    quote = response.json()
    assert quote["status"] == "priced"
    assert quote["price"] == 8.0  # GPU base price (2.0) * 4 hours

    # Verify negotiation log
    assert len(quote["negotiation_log"]) == 1
    assert quote["negotiation_log"][0]["role"] == "seller"
    assert quote["negotiation_log"][0]["price"] == 8.0


@pytest.mark.unit
def test_invalid_quote_request(client):
    """Test validation of quote request parameters."""
    response = client.post(
        "/quotes/request",
        json={
            "buyer_id": "bob",
            "resource_type": "GPU",
            # duration_hours omitted
            "buyer_max_price": 10.0,  # Add required field
        },
    )
    assert response.status_code == 422
    # Optionally check the details in the response:
    body = response.json()
    assert "detail" in body
    # The Pydantic validation error typically includes the field name:
    assert any(err["loc"][-1] == "duration_hours" for err in body["detail"])


# Integration tests using PostgreSQL
@pytest.mark.integration
def test_quote_workflow_postgres(client):
    """Test the full quote workflow from request to acceptance (PostgreSQL)."""
    # Create quote request
    response = client.post(
        "/quotes/request",
        json={
            "buyer_id": "test_buyer",
            "resource_type": "GPU",
            "duration_hours": 4,
        },
    )
    assert response.status_code == 201
    quote_id = response.json()["quote_id"]

    # Get quote details
    quote = client.get(f"/quotes/{quote_id}")
    assert quote.status_code == 200
    assert quote.json()["status"] == "pending"

    # Negotiate quote
    nego = client.post(f"/quotes/{quote_id}/negotiate")
    assert nego.status_code == 200
    data = nego.json()
    assert data["status"] == "priced"
    assert data["price"] == 8.0  # GPU base price (2.0) * 4 hours

    # Try negotiating again - should fail
    nego2 = client.post(f"/quotes/{quote_id}/negotiate")
    assert nego2.status_code == 409
    assert "not in pending status" in nego2.json()["detail"]


@pytest.mark.integration
@pytest.mark.slow
def test_concurrent_quote_requests_postgres(postgres_client):
    """Test handling of concurrent quote requests with PostgreSQL."""
    import concurrent.futures

    results = []

    def create_quote(buyer_id: str):
        response = postgres_client.post(
            "/quotes/request",
            json={
                "buyer_id": f"concurrent_{buyer_id}",
                "resource_type": "CPU",
                "duration_hours": 2,
                "buyer_max_price": 5.0,  # Add required field
            },
        )
        return response.status_code, response.json()

    # Create multiple quotes concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_quote, f"buyer_{i}") for i in range(10)]
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    # All should succeed
    for status_code, response_data in results:
        assert status_code == 201
        assert "quote_id" in response_data
        assert response_data["quote_id"] > 0


# Legacy test fixture for backward compatibility
@pytest.fixture
def test_db():
    """Legacy test database fixture - kept for backward compatibility."""
    import os

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
