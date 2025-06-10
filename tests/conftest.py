"""Test configuration and fixtures."""

import os
import pytest
from fastapi.testclient import TestClient
from main import app
from core.settings import Settings
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from db.models import Base
from langchain_core.messages import AIMessage
import json


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
                response = (
                    "accept" if price <= max_price else str(price * 0.8)
                )  # Counter with 80% of price
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
                return OpenAIResponse(str(price))

            return OpenAIResponse("10.0")  # Fallback response

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
            "STRIPE_KEY": "sk_test_dummy",
            "PAYPAL_CLIENT_ID": "test_client_id",
            "PAYPAL_SECRET": "test_secret",
            "OPENAI_API_KEY": "sk-test-dummy",
            "APP_NAME": "Test Marketplace",
            "ENVIRONMENT": "development",
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
        STRIPE_KEY="sk_test_mock",
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
    return Settings(
        DATABASE_URL="postgresql://sanchitkumar@localhost:5432/test_agent_marketplace",
        STRIPE_KEY="sk_test_mock",
        PAYPAL_CLIENT_ID="test_client_id",
        PAYPAL_SECRET="test_secret",
        OPENAI_API_KEY="sk-test-mock",
        APP_NAME="Test Marketplace",
        DEBUG=True,
        ENVIRONMENT="development",
        MCP_POSTGRES_HOST="localhost",
        MCP_POSTGRES_PORT=5432,
        MCP_POSTGRES_DB="test_agent_marketplace",
        MCP_POSTGRES_USER="sanchitkumar",
        MCP_POSTGRES_PASSWORD="",
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
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def client(mock_settings, test_db_engine):
    """Test client with proper database setup."""
    from db.session import get_db, reset_engines

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

    with patch("core.dependencies._settings", mock_settings):
        with TestClient(app) as test_client:
            yield test_client

    # Clean up
    app.dependency_overrides.clear()
    reset_engines()


@pytest.fixture
def postgres_client(postgres_test_settings):
    """Client for PostgreSQL integration tests."""
    from db.session import get_db, get_engine, reset_engines

    # Reset any existing engines to ensure clean state
    reset_engines()

    # Initialize the database with tables for PostgreSQL tests
    try:
        # Create engine and initialize tables
        engine = get_engine(postgres_test_settings)
        Base.metadata.create_all(engine)
    except Exception as e:
        pytest.skip(f"PostgreSQL database not available: {e}")

    # Create a session factory bound to the test engine
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

    with patch("core.dependencies._settings", postgres_test_settings):
        with TestClient(app) as test_client:
            yield test_client

    # Clean up
    app.dependency_overrides.clear()
    reset_engines()  # Clean up after test


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
