"""
Agent Compute Marketplace - Main Application Entry Point

This module initializes the FastAPI application and sets up the core routing.
It serves as the main entry point for the agent-based compute marketplace,
where AI agents negotiate cloud compute resources and handle payments.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Agent Compute Marketplace",
    description="AI-powered marketplace for negotiating cloud compute resources",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API status."""
    return {"status": "healthy", "service": "agent-compute-marketplace"}
