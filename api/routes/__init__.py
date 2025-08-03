"""
API Routes Package

This module consolidates all API routes for the agent compute marketplace.
"""

from fastapi import APIRouter

from . import quotes
from . import resources

# Create main router
router = APIRouter()

# Include all route modules
router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
router.include_router(resources.router, prefix="/resources", tags=["resources"])

# Export for use in main application
__all__ = ["router"]
