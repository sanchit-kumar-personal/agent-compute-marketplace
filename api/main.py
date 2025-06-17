"""
Main FastAPI Application Module
"""

from fastapi import FastAPI
from api.routes import quotes
from api import webhooks

app = FastAPI(title="Agent Compute Marketplace")

# Include routers
app.include_router(quotes.router, prefix="/api", tags=["quotes"])
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])


@app.get("/")
async def root():
    return {"message": "Welcome to Agent Compute Marketplace API"}
