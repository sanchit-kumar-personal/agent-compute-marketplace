import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

# Load .env file automatically
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # MCP Configuration
    MCP_SERVER_URL: str = "http://localhost:3001"
    MCP_POSTGRES_HOST: str = "localhost"
    MCP_POSTGRES_PORT: int = 5432
    MCP_POSTGRES_DB: str = "agent_marketplace"
    MCP_POSTGRES_USER: str = "postgres"
    MCP_POSTGRES_PASSWORD: str = ""

    # Payment providers
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    PAYPAL_CLIENT_ID: str
    PAYPAL_SECRET: str

    # OpenAI
    OPENAI_API_KEY: str

    # App settings
    APP_NAME: str = "Agent Compute Marketplace"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "production"] = "development"

    # API Configuration (used by dashboard)
    API_BASE: str = "http://localhost:8000"

    # Observability (Optional)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "agent-compute-marketplace"
    OTEL_RESOURCE_ATTRIBUTES: str = (
        "service.name=agent-compute-marketplace,service.version=0.1.0"
    )

    # Metrics (Optional)
    METRICS_ENABLED: bool = True
    PROMETHEUS_ENDPOINT: str = "http://localhost:9090"

    model_config = ConfigDict(env_file=".env", case_sensitive=True)

    def __init__(self, **kwargs):
        # Check for DATABASE_URL before calling parent constructor
        if not os.getenv("DATABASE_URL"):
            raise RuntimeError(
                "DATABASE_URL not set; create .env or export the variable"
            )
        super().__init__(**kwargs)
