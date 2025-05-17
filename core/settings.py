from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import Literal

# Load .env file automatically
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str

    # Payment providers
    STRIPE_KEY: str
    PAYPAL_CLIENT_ID: str
    PAYPAL_SECRET: str

    # OpenAI
    OPENAI_API_KEY: str

    # App settings
    APP_NAME: str = "Agent Compute Marketplace"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "production"] = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True
