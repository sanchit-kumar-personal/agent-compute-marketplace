"""
Resource Management Routes

This module handles compute resource inventory and availability tracking
for the agent compute marketplace.
"""

from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional
import random

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_async_db
from db.models import Quote
import structlog
from core.metrics import inventory_available

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Resources"])


class ResourceAvailability(BaseModel):
    """Resource availability model."""

    resource_type: str
    available_units: int
    total_units: int
    utilization_percent: float
    base_price_per_hour: float
    current_price_per_hour: float
    demand_multiplier: float
    region: str


# Base resource configuration
BASE_RESOURCE_CONFIG = {
    "GPU": {
        "total_units": 100,
        "base_price": 2.5,
        "specs": {
            "cpu_cores": 8,
            "memory_gb": 32,
            "gpu_model": "V100",
            "storage_gb": 100,
            "network_bandwidth": "10 Gbps",
        },
    },
    "CPU": {
        "total_units": 500,
        "base_price": 0.8,
        "specs": {
            "cpu_cores": 16,
            "memory_gb": 64,
            "gpu_model": None,
            "storage_gb": 200,
            "network_bandwidth": "1 Gbps",
        },
    },
    "TPU": {
        "total_units": 50,
        "base_price": 6.0,
        "specs": {
            "cpu_cores": 4,
            "memory_gb": 16,
            "gpu_model": "TPUv4",
            "storage_gb": 50,
            "network_bandwidth": "100 Gbps",
        },
    },
}


async def _calculate_demand_multipliers(db: AsyncSession) -> Dict[str, float]:
    """Calculate demand multipliers based on recent quote activity."""
    # Get quotes from last 24 hours
    result = await db.execute(
        select(Quote).filter(
            Quote.created_at >= datetime.now(UTC) - timedelta(hours=24)
        )
    )
    recent_quotes = result.scalars().all()

    # Count by resource type
    demand_counts = {}
    for quote in recent_quotes:
        resource_type = quote.resource_type
        demand_counts[resource_type] = demand_counts.get(resource_type, 0) + 1

    # Convert to multipliers
    multipliers = {}
    for resource_type in BASE_RESOURCE_CONFIG.keys():
        count = demand_counts.get(resource_type, 0)
        if count > 10:
            multipliers[resource_type] = 1.3  # High demand
        elif count > 5:
            multipliers[resource_type] = 1.1  # Normal demand
        else:
            multipliers[resource_type] = 0.9  # Low demand

    return multipliers


def get_current_availability(
    resource_type: str, base_config: dict, db: Session = None
) -> int:
    """Get current availability for a resource type with realistic variation."""
    base_available = base_config["total_units"]

    # Add some realistic variation (-20% to +5%)
    variation = random.randint(-int(base_available * 0.2), int(base_available * 0.05))

    # Ensure we don't go below 0 or above total units
    return max(0, min(base_available + variation, base_config["total_units"]))


@router.get("/availability", response_model=List[ResourceAvailability])
async def get_resource_availability(
    resource_type: Optional[str] = Query(None),
    region: str = Query("us-east-1"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get current resource availability and pricing."""
    # Calculate demand multipliers based on recent quote activity
    demand_multipliers = await _calculate_demand_multipliers(db)

    availabilities = []

    for res_type, config in BASE_RESOURCE_CONFIG.items():
        if resource_type and res_type != resource_type:
            continue

        # Get current availability (doesn't mutate global state)
        available_units = get_current_availability(res_type, config, db)

        # Update Prometheus inventory gauge
        inventory_available.labels(resource_type=res_type.lower()).set(available_units)

        utilization = (
            (config["total_units"] - available_units) / config["total_units"]
        ) * 100

        # Calculate dynamic pricing
        demand_multiplier = demand_multipliers.get(res_type, 1.0)
        scarcity_multiplier = 1.0 + (utilization / 100) * 0.5  # Up to 50% premium

        current_price = config["base_price"] * demand_multiplier * scarcity_multiplier

        availability = ResourceAvailability(
            resource_type=res_type,
            available_units=available_units,
            total_units=config["total_units"],
            utilization_percent=round(utilization, 1),
            base_price_per_hour=config["base_price"],
            current_price_per_hour=round(current_price, 2),
            demand_multiplier=round(demand_multiplier, 2),
            region=region,
        )

        availabilities.append(availability)

    return availabilities
