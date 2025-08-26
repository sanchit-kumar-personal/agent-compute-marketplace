"""Test configuration and fixtures."""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.settings import Settings
from db.models import Base
from main import app


class OpenAIResponse:
    def __init__(self, content):
        self.choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Message", (), {"content": content, "role": "assistant"}
                    )()
                },
            )()
        ]

    def model_dump(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": self.choices[0].message.content,
                        "role": self.choices[0].message.role,
                    }
                }
            ]
        }


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Mock LLM for all tests."""

    class DummyChatOpenAI:
        def __init__(self, *args, **kwargs):
            pass

        async def ainvoke(self, messages, *args, **kwargs):
            """Mock price generation to match fallback pricing."""
            # Extract quote details from the user message
            user_msg = [m for m in messages if m.type == "human"][0].content
            quote = json.loads(user_msg)

            # Use same pricing logic as fallback
            base_prices = {
                "GPU": 2.0,
                "CPU": 0.5,
                "TPU": 5.0,
            }
            base_price = base_prices.get(quote["resource_type"].upper(), 1.0)
            price = base_price * quote["duration_hours"]
            return AIMessage(content=str(price))

    class DummyAsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = type(
                "Chat",
                (),
                {"completions": type("Completions", (), {"create": self.create})()},
            )()

        async def create(self, *args, **kwargs):
            # Extract quote details from the messages
            messages = kwargs.get("messages", [])
            system_msg = next(m["content"] for m in messages if m["role"] == "system")
            user_msg = next(m["content"] for m in messages if m["role"] == "user")

            # Parse user message
            data = json.loads(user_msg)

            # If this is a buyer response (has seller_price)
            if "seller_price" in data:
                # Extract max price from system prompt
                import re

                max_price = float(re.search(r"<= (\d+\.?\d*)", system_msg).group(1))
                price = data["seller_price"]

                # Return structured JSON response matching BuyerReply schema
                if price <= max_price:
                    response = json.dumps(
                        {
                            "action": "accept",
                            "price": None,
                            "reason": "Price is within budget",
                        }
                    )
                else:
                    counter_price = round(price * 0.8, 2)
                    response = json.dumps(
                        {
                            "action": "counter_offer",
                            "price": counter_price,
                            "reason": f"Counter-offering {counter_price}",
                        }
                    )
                return OpenAIResponse(response)

            # If this is a seller quote (has resource_type)
            if "resource_type" in data:
                base_prices = {
                    "GPU": 2.0,
                    "CPU": 0.5,
                    "TPU": 5.0,
                }
                base_price = base_prices.get(data["resource_type"].upper(), 1.0)
                price = base_price * data["duration_hours"]

                # Return structured JSON response matching SellerReply schema
                response = json.dumps(
                    {
                        "action": "counter_offer",
                        "price": price,
                        "reason": f"Base pricing for {data['resource_type']}",
                    }
                )
                return OpenAIResponse(response)

            # Fallback response
            response = json.dumps(
                {"action": "counter_offer", "price": 10.0, "reason": "Fallback pricing"}
            )
            return OpenAIResponse(response)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", DummyChatOpenAI)
    monkeypatch.setattr("openai.AsyncOpenAI", DummyAsyncOpenAI)
    yield


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables before each test."""
    # Store original env vars
    original_env = dict(os.environ)

    # Set test environment variables
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///:memory:",  # Use in-memory for faster tests
            "STRIPE_API_KEY": "sk_test_dummy",
            "STRIPE_WEBHOOK_SECRET": "whsec_test_dummy",
            "PAYPAL_CLIENT_ID": "test_client_id",
            "PAYPAL_SECRET": "test_secret",
            "OPENAI_API_KEY": "sk-test-dummy",
            "APP_NAME": "Test Marketplace",
            "ENVIRONMENT": "development",  # Use development environment for tests
            "DEBUG": "true",
        }
    )

    yield

    # Restore original env vars
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_settings():
    return Settings(
        DATABASE_URL="sqlite:///:memory:",
        STRIPE_API_KEY="sk_test_mock",
        STRIPE_WEBHOOK_SECRET="whsec_test_mock",
        PAYPAL_CLIENT_ID="test_client_id",
        PAYPAL_SECRET="test_secret",
        OPENAI_API_KEY="sk-test-mock",
        APP_NAME="Test Marketplace",
        DEBUG=True,
        ENVIRONMENT="development",
    )


@pytest.fixture
def postgres_test_settings():
    """Settings for PostgreSQL integration tests."""
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "DATABASE_URL", "postgresql://sanchitkumar@localhost:5432/agent_marketplace"
        ),
    )
    return Settings(
        DATABASE_URL=db_url,
        STRIPE_API_KEY="sk_test_mock",
        PAYPAL_CLIENT_ID="test_client_id",
        PAYPAL_SECRET="test_secret",
        OPENAI_API_KEY="sk-test-mock",
        APP_NAME="Test Marketplace",
        DEBUG=True,
        ENVIRONMENT="development",
    )


@pytest.fixture
def test_db_engine(mock_settings):
    """Create a test database engine and setup tables."""
    # Use StaticPool and check_same_thread=False for SQLite testing
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    # Add test compute resources to the shared database
    from sqlalchemy.orm import sessionmaker
    from db.models import ComputeResource

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    test_resources = [
        ComputeResource(
            type="GPU",
            specs='{"memory": "16GB", "cores": 8}',
            status="available",
            price_per_hour=2.5,
        ),
        ComputeResource(
            type="GPU",
            specs='{"memory": "32GB", "cores": 16}',
            status="available",
            price_per_hour=5.0,
        ),
        ComputeResource(
            type="CPU",
            specs='{"cores": 4, "memory": "8GB"}',
            status="available",
            price_per_hour=0.8,
        ),
        ComputeResource(
            type="TPU",
            specs='{"version": "v4", "memory": "64GB"}',
            status="available",
            price_per_hour=6.0,
        ),
    ]

    for resource in test_resources:
        session.add(resource)
    session.commit()
    session.close()

    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Create test database session using the shared engine."""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_compute_resources(test_db_session):
    """Create test ComputeResource records for tests."""
    from db.models import ComputeResource
    from datetime import UTC, datetime

    # Create test resources
    resources = []

    # GPU resources (10 units)
    for i in range(10):
        gpu = ComputeResource(
            type="GPU",
            specs='{"gpu_model": "NVIDIA A100", "memory_gb": 80}',
            price_per_hour=2.5,
            status="available",
            created_at=datetime.now(UTC),
        )
        resources.append(gpu)
        test_db_session.add(gpu)

    # CPU resources (50 units)
    for i in range(50):
        cpu = ComputeResource(
            type="CPU",
            specs='{"cpu_cores": 16, "memory_gb": 64}',
            price_per_hour=0.8,
            status="available",
            created_at=datetime.now(UTC),
        )
        resources.append(cpu)
        test_db_session.add(cpu)

    # TPU resources (5 units)
    for i in range(5):
        tpu = ComputeResource(
            type="TPU",
            specs='{"tpu_model": "TPU v4", "memory_gb": 128}',
            price_per_hour=6.0,
            status="available",
            created_at=datetime.now(UTC),
        )
        resources.append(tpu)
        test_db_session.add(tpu)

    test_db_session.commit()
    return resources


@pytest.fixture
def client(mock_settings, test_db_engine):
    """Test client with proper database setup."""
    from db.session import get_db, get_async_db, reset_engines
    from starlette.concurrency import run_in_threadpool

    # Reset engines to ensure clean state
    reset_engines()

    # Create a session factory bound to the test engine
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db

    async def override_get_async_db():
        # Wrap sync session with async-like adapter for routes expecting AsyncSession
        db = TestingSessionLocal()

        class AsyncSessionAdapter:
            def __init__(self, inner):
                self._inner = inner

            def add(self, instance):
                return self._inner.add(instance)

            def add_all(self, instances):
                return self._inner.add_all(instances)

            async def commit(self):
                await run_in_threadpool(self._inner.commit)

            async def rollback(self):
                await run_in_threadpool(self._inner.rollback)

            async def refresh(self, instance):
                await run_in_threadpool(lambda: self._inner.refresh(instance))

            async def get(self, model, ident):
                return await run_in_threadpool(lambda: self._inner.get(model, ident))

            async def execute(self, statement):
                return await run_in_threadpool(lambda: self._inner.execute(statement))

            async def close(self):
                await run_in_threadpool(self._inner.close)

        adapter = AsyncSessionAdapter(db)
        try:
            yield adapter
        finally:
            await run_in_threadpool(db.close)

    app.dependency_overrides[get_async_db] = override_get_async_db

    with patch("core.dependencies._settings", mock_settings):
        with TestClient(app) as test_client:
            yield test_client

    # Clean up
    app.dependency_overrides.clear()
    reset_engines()


@pytest.fixture
def postgres_client(postgres_test_settings):
    """Client for PostgreSQL integration tests."""
    from db.session import get_db, get_async_db, get_engine, reset_engines
    from starlette.concurrency import run_in_threadpool

    # Reset engines to ensure clean state
    reset_engines()

    # Get PostgreSQL engine
    engine = get_engine(postgres_test_settings)

    # Create all tables
    Base.metadata.drop_all(engine)  # Drop existing tables
    Base.metadata.create_all(engine)  # Create fresh tables

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db

    async def override_get_async_db():
        db = TestingSessionLocal()

        class AsyncSessionAdapter:
            def __init__(self, inner):
                self._inner = inner

            def add(self, instance):
                return self._inner.add(instance)

            def add_all(self, instances):
                return self._inner.add_all(instances)

            async def commit(self):
                await run_in_threadpool(self._inner.commit)

            async def rollback(self):
                await run_in_threadpool(self._inner.rollback)

            async def refresh(self, instance):
                await run_in_threadpool(lambda: self._inner.refresh(instance))

            async def get(self, model, ident):
                return await run_in_threadpool(lambda: self._inner.get(model, ident))

            async def execute(self, statement):
                return await run_in_threadpool(lambda: self._inner.execute(statement))

            async def close(self):
                await run_in_threadpool(self._inner.close)

        adapter = AsyncSessionAdapter(db)
        try:
            yield adapter
        finally:
            await run_in_threadpool(db.close)

    app.dependency_overrides[get_async_db] = override_get_async_db

    with patch("core.dependencies._settings", postgres_test_settings):
        with TestClient(app) as test_client:
            yield test_client

    # Clean up
    app.dependency_overrides.clear()
    reset_engines()
    Base.metadata.drop_all(engine)  # Clean up tables


@pytest.fixture(autouse=True)
def mock_stripe_setup():
    """Mock Stripe API for all tests."""
    with (
        patch("stripe.api_key", "sk_test_mock"),
        patch("stripe.PaymentIntent.create") as mock_create,
    ):
        mock_create.return_value = type(
            "PaymentIntent", (), {"id": "pi_mock", "status": "requires_payment_method"}
        )()
        yield mock_create


# Pytest markers for different test types
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (PostgreSQL)"
    )
    config.addinivalue_line("markers", "unit: marks tests as unit tests (SQLite)")
    config.addinivalue_line("markers", "slow: marks tests as slow running")


# Legacy test fixture for backward compatibility
@pytest.fixture
def test_db():
    """Legacy test database fixture - kept for backward compatibility."""
    import os

    from db.session import get_db

    # Set up in-memory database
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Override the get_db dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # Replace the dependency
    app.dependency_overrides[get_db] = override_get_db

    yield  # Run the tests

    # Cleanup
    app.dependency_overrides.clear()
    engine.dispose()
    if old_db_url:
        os.environ["DATABASE_URL"] = old_db_url
