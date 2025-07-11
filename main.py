"""
Agent Compute Marketplace - Main Application Entry Point

This module initializes the FastAPI application and sets up the core routing.
It serves as the main entry point for the agent-based compute marketplace,
where AI agents negotiate cloud compute resources and handle payments.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from api import routes, webhooks
from api.middleware import log_api_entry
from api.routes.quotes import router as quotes_router
from core.audit import AuditMiddleware
from core.dependencies import clear_settings, get_settings, init_settings
from core.logging import configure_logging
from core.metrics import add_metrics_auth_middleware, init_metrics
from core.settings import Settings
from core.tracing import init_tracer
from db.session import init_async_db, init_db
from negotiation import router as negotiation_router


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
        print(f"Async database initialization failed, falling back to sync: {e}")
        init_db(settings)

    yield
    # Shutdown
    clear_settings()


app = FastAPI(
    title="Agent Compute Marketplace",
    description="A marketplace for agent-based negotiations with PostgreSQL MCP support",
    version="0.1.0",
    lifespan=lifespan,
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
    """Root endpoint providing API information."""
    return {
        "name": "Agent Compute Marketplace",
        "version": "0.1.0",
        "description": "A marketplace for agent-based negotiations with PostgreSQL MCP support",
        "endpoints": {
            "healthz": "Health check endpoint",
            "negotiation": "Negotiation related endpoints",
            "api": "API endpoints",
        },
    }


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


# Include routers
app.include_router(negotiation_router, prefix="/negotiation")
app.include_router(routes.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(quotes_router, prefix="/quotes", tags=["quotes"])


def main():
    configure_logging()
    if __name__ == "__main__":
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
