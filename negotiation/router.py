"""
Negotiation Router Module

This module defines the FastAPI router for negotiation-related endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .engine import NegotiationEngine

router = APIRouter(tags=["Negotiation"])
engine = NegotiationEngine()


class NegotiationRequest(BaseModel):
    """Request model for starting a negotiation."""

    compute_requirements: dict
    budget_constraints: dict
    time_constraints: dict | None = None


class NegotiationResponse(BaseModel):
    """Response model for negotiation results."""

    negotiation_id: str
    status: str
    offer: dict | None = None


@router.post("/start", response_model=NegotiationResponse)
async def start_negotiation(request: NegotiationRequest):
    """Start a new negotiation process."""
    try:
        negotiation = engine.start_negotiation(
            compute_requirements=request.compute_requirements,
            budget_constraints=request.budget_constraints,
            time_constraints=request.time_constraints,
        )
        return NegotiationResponse(
            negotiation_id=negotiation["id"],
            status="started",
            offer=negotiation.get("initial_offer"),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{negotiation_id}", response_model=NegotiationResponse)
async def get_negotiation_status(negotiation_id: str):
    """Get the status of an ongoing negotiation."""
    try:
        status = engine.get_negotiation_status(negotiation_id)
        return NegotiationResponse(
            negotiation_id=negotiation_id,
            status=status["status"],
            offer=status.get("current_offer"),
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
