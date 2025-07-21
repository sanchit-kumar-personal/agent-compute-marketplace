"""
API routes initialization
"""

from fastapi import APIRouter

from .quotes import router as quotes_router

router = APIRouter()
router.include_router(quotes_router, prefix="/quotes", tags=["quotes"])
