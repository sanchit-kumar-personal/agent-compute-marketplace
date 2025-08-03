"""
Agent Compute Marketplace - Main Application Entry Point

This module initializes the FastAPI application and sets up the core routing.
It serves as the main entry point for the agent-based compute marketplace,
where AI agents negotiate cloud compute resources and handle payments.
"""

import structlog
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from api import routes
from api.middleware import log_api_entry
from core.audit import AuditMiddleware
from core.dependencies import clear_settings, get_settings, init_settings
from core.logging import configure_logging
from core.metrics import add_metrics_auth_middleware, init_metrics
from core.settings import Settings
from core.tracing import init_tracer
from db.session import init_async_db, init_db

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application startup and shutdown events."""
    # Startup
    init_settings()
    settings = get_settings()

    # Initialize OpenTelemetry tracing
    init_tracer()

    # Initialize database (try async first, fallback to sync)
    try:
        if settings.DATABASE_URL.startswith("postgresql"):
            await init_async_db(settings)
        else:
            init_db(settings)
    except Exception as e:
        # Fallback to sync initialization
        log.warning(
            "Async database initialization failed, falling back to sync", error=str(e)
        )
        init_db(settings)

    yield
    # Shutdown
    clear_settings()


app = FastAPI(
    title="Agent Compute Marketplace",
    description="""
    ## AI-Powered Compute Resource Marketplace

    A sophisticated marketplace where AI agents autonomously negotiate cloud compute resources with real-time payment processing.

    ### Key Features:
    - **AI-Powered Negotiations**: Sophisticated buyer/seller agents with market awareness
    - **Real-Time Pricing**: Dynamic pricing based on demand, scarcity, and market conditions
    - **Payment Integration**: Stripe PaymentIntent and PayPal Invoice creation
    - **Market Analytics**: Real-time market insights and price trend analysis
    - **Enterprise Ready**: Audit logging, metrics, tracing, and comprehensive error handling

    ### Use Cases:
    - Automated cloud resource procurement
    - Dynamic pricing optimization
    - Multi-party negotiations
    - Market analysis and forecasting
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Initialize FastAPI instrumentation
FastAPIInstrumentor.instrument_app(app)

# Initialize Prometheus metrics
init_metrics(app)

# Add metrics authentication middleware (for production)
add_metrics_auth_middleware(app)

# Add logging middleware first
app.middleware("http")(log_api_entry)

# Add audit middleware
app.add_middleware(AuditMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


@app.get("/")
async def root():
    """Root endpoint providing comprehensive API information."""
    return {
        "name": "Agent Compute Marketplace",
        "version": "1.0.0",
        "description": "AI-Powered Compute Resource Marketplace with autonomous agent negotiations",
        "features": [
            "AI-powered buyer/seller agent negotiations",
            "Real-time dynamic pricing with market awareness",
            "Stripe and PayPal payment processing",
            "Comprehensive audit logging and monitoring",
        ],
        "api_documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json",
        },
        "endpoints": {
            "app": "/api/v1/ - Core API endpoints",
            "docs": "/docs - Interactive API documentation",
            "redoc": "/redoc - Alternative API documentation",
            "quotes": "/api/v1/quotes/ - Quote management and negotiation",
            "resources": "/api/v1/resources/ - Resource availability",
            "payments": "/api/v1/quotes/{id}/payments - Payment processing",
            "health": "/health - Health check endpoint",
            "metrics": "/metrics - Prometheus metrics (requires auth)",
        },
        "demo_workflow": {
            "1": "POST /api/v1/quotes/request - Create a quote request",
            "2": "POST /api/v1/quotes/{id}/negotiate/auto - AI negotiation + payment",
            "3": "GET /api/v1/quotes/recent - View recent quotes",
        },
    }


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    """Health check endpoint alias."""
    return await health_check(settings)


@app.get("/healthz")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint to verify API status."""
    db_type = (
        "PostgreSQL" if settings.DATABASE_URL.startswith("postgresql") else "SQLite"
    )
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "database": db_type,
        "environment": settings.ENVIRONMENT,
    }


# Include routers under a single versioned prefix
API_PREFIX = "/api/v1"

# Core API (quotes, resources, etc.)
app.include_router(routes.router, prefix=API_PREFIX)


def main():
    configure_logging()
    if __name__ == "__main__":
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
