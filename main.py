"""
Agent Compute Marketplace - Main Application Entry Point

This module initializes the FastAPI application and sets up the core routing.
It serves as the main entry point for the agent-based compute marketplace,
where AI agents negotiate cloud compute resources and handle payments.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.settings import Settings
from negotiation import router as negotiation_router

# Settings dependency
_settings = None


def get_settings() -> Settings:
    """Dependency that provides application settings."""
    assert (
        _settings is not None
    ), "Settings not initialized. Make sure startup() was called."
    return _settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application startup and shutdown events."""
    # Startup
    global _settings
    _settings = Settings()
    yield
    # Shutdown
    _settings = None


app = FastAPI(
    title="Agent Compute Marketplace",
    description="A marketplace for agent-based negotiations",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "description": "A marketplace for agent-based negotiations",
        "endpoints": {
            "healthz": "Health check endpoint",
            "negotiation": "Negotiation related endpoints",
        },
    }


@app.get("/healthz")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint to verify API status."""
    return {"status": "ok", "app_name": settings.APP_NAME}


# Include routers
app.include_router(negotiation_router, prefix="/negotiation")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
