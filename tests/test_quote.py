"""
Tests for the quote workflow functionality.
"""

import pytest
from main import app
from db.models import Base
from db.session import get_db
from core.dependencies import init_settings, clear_settings
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


# Unit tests using SQLite
@pytest.mark.unit
def test_quote_workflow(client):
    """Test the happy path of the quote workflow."""
    # Create a quote request
    response = client.post(
        "/api/quote-request",
        json={"buyer_id": "alice", "resource_type": "GPU", "duration_hours": 4},
    )
    assert response.status_code == 201
    quote_id = response.json()["quote_id"]
    assert quote_id > 0

    # Get the quote details - should be pending initially
    response = client.get(f"/api/quote/{quote_id}")
    assert response.status_code == 200
    quote = response.json()
    assert quote["status"] == "pending"  # Quote starts in pending state
    assert quote["duration_hours"] == 4
    assert quote["price"] == 0.0  # No price set yet

    # Negotiate the quote
    response = client.post(f"/api/quote/{quote_id}/negotiate")
    assert response.status_code == 200
    quote = response.json()
    assert quote["status"] == "priced"  # Now it should be priced
    assert quote["price"] == 6.0  # 1.50 * 4 hours from SellerAgent.generate_quote()
    assert len(quote["negotiation_log"]) == 1  # One negotiation message


@pytest.mark.unit
def test_quote_missing_duration_field(client):
    """Test that missing duration_hours field returns 422 Unprocessable Entity."""
    # Missing "duration_hours" should return 422 Unprocessable Entity
    response = client.post(
        "/api/quote-request",
        json={
            "buyer_id": "bob",
            "resource_type": "GPU",
            # duration_hours omitted
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
def test_quote_workflow_postgres(postgres_client):
    """Test quote workflow with PostgreSQL backend."""
    # This test will use the actual PostgreSQL database
    # Create a quote request
    response = postgres_client.post(
        "/api/quote-request",
        json={
            "buyer_id": "postgres_alice",
            "resource_type": "GPU",
            "duration_hours": 8,
        },
    )
    assert response.status_code == 201
    quote_id = response.json()["quote_id"]
    assert quote_id > 0

    # Get the quote details
    response = postgres_client.get(f"/api/quote/{quote_id}")
    assert response.status_code == 200
    quote = response.json()
    assert quote["status"] == "pending"
    assert quote["buyer_id"] == "postgres_alice"
    assert quote["duration_hours"] == 8

    # Negotiate the quote
    response = postgres_client.post(f"/api/quote/{quote_id}/negotiate")
    assert response.status_code == 200
    quote = response.json()
    assert quote["status"] == "priced"
    assert quote["price"] == 12.0  # 1.50 * 8 hours


@pytest.mark.integration
@pytest.mark.slow
def test_concurrent_quote_requests_postgres(postgres_client):
    """Test handling of concurrent quote requests with PostgreSQL."""
    import concurrent.futures

    results = []

    def create_quote(buyer_id: str):
        response = postgres_client.post(
            "/api/quote-request",
            json={
                "buyer_id": f"concurrent_{buyer_id}",
                "resource_type": "CPU",
                "duration_hours": 2,
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
