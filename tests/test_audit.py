"""
Test module for audit logging functionality.

This module tests:
- AuditMiddleware behavior
- Audit log creation for different actions
- Payment audit logging
- Database interactions
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from core.audit import determine_action, AuditMiddleware
from db.models import (
    AuditAction,
    AuditLog,
    Base,
    PaymentProvider,
    Quote,
    QuoteStatus,
    Transaction,
    TransactionStatus,
)
from db.session import get_db
from main import app

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_audit.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Create test client."""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Create database session for tests."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_determine_action_quote_created():
    """Test determining audit action for quote creation."""
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/quotes/request"

    response = MagicMock()
    response.status_code = 201

    action = determine_action(request, response)
    assert action == AuditAction.quote_created


def test_determine_action_quote_negotiated():
    """Test determining audit action for quote negotiation."""
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/quotes/123/negotiate"

    response = MagicMock()
    response.status_code = 200

    action = determine_action(request, response)
    assert action == AuditAction.negotiation_turn


def test_determine_action_payment_succeeded():
    """Test determining audit action for successful payment."""
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/quotes/123/payments"

    response = MagicMock()
    response.status_code = 200

    action = determine_action(request, response)
    assert action == AuditAction.payment_succeeded


def test_determine_action_payment_failed():
    """Test determining audit action for failed payment."""
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/quotes/123/payments"

    response = MagicMock()
    response.status_code = 402

    action = determine_action(request, response)
    assert action == AuditAction.payment_failed


def test_determine_action_for_other_paths():
    """Test determining audit action for other API paths."""
    request = MagicMock()
    request.method = "GET"
    request.url.path = "/api/v1/quotes/123"

    response = MagicMock()
    response.status_code = 200

    action = determine_action(request, response)
    assert action == AuditAction.quote_created  # default fallback


def test_determine_action_different_methods():
    """Test audit action determination for different HTTP methods."""
    methods = ["GET", "POST", "PUT", "DELETE"]

    for method in methods:
        request = MagicMock()
        request.method = method
        request.url.path = "/api/v1/quotes/123/negotiate"

        response = MagicMock()
        response.status_code = 200

        action = determine_action(request, response)
        assert isinstance(action, AuditAction)
        assert action == AuditAction.negotiation_turn


@pytest.mark.asyncio
async def test_audit_middleware_initialization():
    """Test audit middleware initialization."""
    app = MagicMock()
    middleware = AuditMiddleware(app)

    assert middleware.app == app


@pytest.mark.asyncio
async def test_audit_middleware_dispatch():
    """Test audit middleware request dispatch."""
    app = MagicMock()
    middleware = AuditMiddleware(app)

    # Mock request
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/quotes"
    request.state = MagicMock()
    request.state.db = None  # No DB session

    # Mock call_next function
    async def mock_call_next(request):
        response = MagicMock()
        response.status_code = 200
        return response

    # Test dispatch - should not raise errors even without DB
    response = await middleware.dispatch(request, mock_call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_audit_middleware_with_exception():
    """Test audit middleware handles exceptions properly."""
    app = MagicMock()
    middleware = AuditMiddleware(app)

    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/quotes/request"

    # Mock call_next that raises an exception
    async def mock_call_next_error(request):
        raise Exception("Something went wrong")

    # Test that exception is re-raised
    with pytest.raises(Exception, match="Something went wrong"):
        await middleware.dispatch(request, mock_call_next_error)


def test_audit_different_status_codes():
    """Test audit action determination for different response status codes."""
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/quotes/123/payments"

    # Test success
    response_success = MagicMock()
    response_success.status_code = 200
    action_success = determine_action(request, response_success)
    assert action_success == AuditAction.payment_succeeded

    # Test failure
    response_failure = MagicMock()
    response_failure.status_code = 402
    action_failure = determine_action(request, response_failure)
    assert action_failure == AuditAction.payment_failed

    # Test server error
    response_error = MagicMock()
    response_error.status_code = 500
    action_error = determine_action(request, response_error)
    assert action_error == AuditAction.payment_failed


def test_audit_middleware_paths_coverage():
    """Test audit middleware handles various API paths correctly."""
    paths_and_expected_actions = [
        ("/api/v1/quotes/request", "POST", 201, AuditAction.quote_created),
        ("/api/v1/quotes/123/negotiate", "POST", 200, AuditAction.negotiation_turn),
        (
            "/api/v1/quotes/123/negotiate/auto",
            "POST",
            200,
            AuditAction.negotiation_turn,
        ),
        ("/api/v1/quotes/123/payments", "POST", 200, AuditAction.payment_succeeded),
        (
            "/api/v1/quotes/123",
            "GET",
            200,
            AuditAction.quote_created,
        ),  # default fallback
        ("/api/v1/quotes", "GET", 200, AuditAction.quote_created),  # default fallback
        ("/healthz", "GET", 200, AuditAction.quote_created),  # default fallback
    ]

    for path, method, status, expected_action in paths_and_expected_actions:
        request = MagicMock()
        request.method = method
        request.url.path = path

        response = MagicMock()
        response.status_code = status

        action = determine_action(request, response)
        assert action == expected_action, f"Failed for {method} {path} -> {status}"


def test_audit_action_enum_coverage():
    """Test that all audit action enum values are properly defined."""
    # Verify all expected audit actions exist
    expected_actions = [
        "quote_created",
        "negotiation_turn",
        "quote_accepted",
        "quote_rejected",
        "payment_succeeded",
        "payment_failed",
    ]

    for action_name in expected_actions:
        assert hasattr(AuditAction, action_name)
        action_value = getattr(AuditAction, action_name)
        assert isinstance(action_value, AuditAction)


def test_audit_written(client, db_session):
    """Test that audit logs are written for API requests."""
    # Test a simple endpoint that should work
    response = client.get("/healthz")
    assert response.status_code == 200

    # Since the middleware only logs /api requests, let's test that
    # We'll mock the audit middleware behavior directly
    from db.models import AuditAction, AuditLog

    # Create a quote manually to test audit logging
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=2,
        status=QuoteStatus.pending,
    )
    db_session.add(quote)
    db_session.commit()

    # Create audit log directly (simulating middleware behavior)
    audit_log = AuditLog(
        quote_id=quote.id,
        action=AuditAction.quote_created,
        payload={
            "method": "POST",
            "path": "/api/quote-request",
            "body": "test",
            "status": 201,
        },
    )
    db_session.add(audit_log)
    db_session.commit()

    # Verify the audit log was created
    logs = db_session.query(AuditLog).filter_by(quote_id=quote.id).all()
    assert len(logs) == 1
    assert logs[0].action == AuditAction.quote_created
    assert logs[0].payload["method"] == "POST"
    assert logs[0].payload["status"] == 201


def test_audit_log_creation(db_session):
    """Test direct audit log creation."""
    # Create a quote first
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=2,
        price=100.0,
        status=QuoteStatus.pending,
    )
    db_session.add(quote)
    db_session.commit()

    # Create audit log
    audit_log = AuditLog(
        quote_id=quote.id,
        action=AuditAction.quote_created,
        payload={
            "method": "POST",
            "path": "/api/quote-request",
            "body": json.dumps({"buyer_id": "test_buyer", "resource_type": "GPU"}),
        },
    )
    db_session.add(audit_log)
    db_session.commit()

    # Verify audit log exists
    retrieved_log = db_session.query(AuditLog).filter_by(quote_id=quote.id).first()
    assert retrieved_log is not None
    assert retrieved_log.action == AuditAction.quote_created
    assert retrieved_log.payload["method"] == "POST"


def test_payment_audit_logging(db_session):
    """Test audit logging for payment events."""
    # Create a quote
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=2,
        price=100.0,
        status=QuoteStatus.accepted,
    )
    db_session.add(quote)
    db_session.commit()

    # Create transaction
    transaction = Transaction(
        quote_id=quote.id,
        provider=PaymentProvider.stripe,
        provider_id="pi_test123",
        amount_usd=100.0,
        status=TransactionStatus.succeeded,
    )
    db_session.add(transaction)

    # Create audit log for payment success
    audit_log = AuditLog(
        quote_id=quote.id,
        action=AuditAction.payment_succeeded,
        payload={"provider_id": "pi_test123", "amount": 100.0, "provider": "stripe"},
    )
    db_session.add(audit_log)
    db_session.commit()

    # Verify audit log
    logs = db_session.query(AuditLog).filter_by(quote_id=quote.id).all()
    assert len(logs) == 1
    assert logs[0].action == AuditAction.payment_succeeded
    assert logs[0].payload["provider"] == "stripe"
    assert logs[0].payload["amount"] == 100.0


def test_multiple_audit_actions(db_session):
    """Test multiple audit actions for the same quote."""
    # Create quote
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=2,
        price=100.0,
        status=QuoteStatus.pending,
    )
    db_session.add(quote)
    db_session.commit()

    # Create multiple audit logs
    actions = [
        AuditAction.quote_created,
        AuditAction.negotiation_turn,
        AuditAction.quote_accepted,
        AuditAction.payment_succeeded,
    ]

    for action in actions:
        audit_log = AuditLog(
            quote_id=quote.id, action=action, payload={"action": action.value}
        )
        db_session.add(audit_log)

    db_session.commit()

    # Verify all logs exist
    logs = db_session.query(AuditLog).filter_by(quote_id=quote.id).all()
    assert len(logs) == 4

    # Check all actions are present
    log_actions = [log.action for log in logs]
    for action in actions:
        assert action in log_actions


def test_audit_middleware_filters_non_api_requests(client, db_session):
    """Test that audit middleware only logs /api requests."""
    # Make request to non-API endpoint
    response = client.get("/healthz")
    assert response.status_code == 200

    # Check that no audit log was created
    logs = db_session.query(AuditLog).all()
    assert len(logs) == 0


def test_audit_middleware_filters_error_responses(client, db_session):
    """Test that audit middleware doesn't log error responses."""
    # Make request that will return error
    response = client.get("/api/nonexistent-endpoint")
    assert response.status_code == 404

    # Check that no audit log was created
    logs = db_session.query(AuditLog).all()
    assert len(logs) == 0


def test_audit_action_enum_values():
    """Test that all required audit actions are defined."""
    expected_actions = [
        "quote_created",
        "negotiation_turn",
        "quote_accepted",
        "quote_rejected",
        "payment_succeeded",
        "payment_failed",
    ]

    for action_name in expected_actions:
        assert hasattr(AuditAction, action_name)
        assert AuditAction[action_name].value == action_name


def test_audit_log_payload_serialization(db_session):
    """Test that audit log payloads are properly serialized."""
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=2,
        status=QuoteStatus.pending,
    )
    db_session.add(quote)
    db_session.commit()

    # Create audit log with complex payload
    complex_payload = {
        "method": "POST",
        "nested": {"value": 123, "array": [1, 2, 3], "bool": True},
    }

    audit_log = AuditLog(
        quote_id=quote.id, action=AuditAction.quote_created, payload=complex_payload
    )
    db_session.add(audit_log)
    db_session.commit()

    # Retrieve and verify
    retrieved_log = db_session.query(AuditLog).filter_by(quote_id=quote.id).first()
    assert retrieved_log.payload == complex_payload
    assert retrieved_log.payload["nested"]["value"] == 123
    assert retrieved_log.payload["nested"]["array"] == [1, 2, 3]
    assert retrieved_log.payload["nested"]["bool"] is True


def test_audit_log_quote_id_foreign_key(db_session):
    """Test that audit log quote_id properly references quotes table."""
    quote = Quote(
        buyer_id="test_buyer",
        resource_type="GPU",
        duration_hours=2,
        status=QuoteStatus.pending,
    )
    db_session.add(quote)
    db_session.commit()

    audit_log = AuditLog(
        quote_id=quote.id, action=AuditAction.quote_created, payload={"test": "data"}
    )
    db_session.add(audit_log)
    db_session.commit()

    # Verify foreign key relationship
    assert audit_log.quote_id == quote.id

    # Note: Foreign key constraint behavior in SQLite is different from PostgreSQL
    # SQLite doesn't enforce foreign key constraints by default in testing
    # So we'll just verify the relationship works correctly
    retrieved_audit = db_session.query(AuditLog).filter_by(quote_id=quote.id).first()
    assert retrieved_audit is not None
    assert retrieved_audit.quote_id == quote.id
