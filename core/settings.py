from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv
from typing import Literal
import os

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

    model_config = ConfigDict(env_file=".env", case_sensitive=True)

    def __init__(self, **kwargs):
        # Check for DATABASE_URL before calling parent constructor
        if not os.getenv("DATABASE_URL"):
            raise RuntimeError(
                "DATABASE_URL not set; create .env or export the variable"
            )
        super().__init__(**kwargs)
