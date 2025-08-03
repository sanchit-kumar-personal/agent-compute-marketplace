"""Tests for resource management endpoints."""

import pytest

BASE = "/api/v1"


@pytest.mark.asyncio
async def test_get_resource_availability(client):
    """Test resource availability endpoint."""
    response = client.get(f"{BASE}/resources/availability")

    assert response.status_code == 200
    data = response.json()

    # Should return availability for all resource types
    assert len(data) == 3  # CPU, GPU, TPU

    resource_types = {r["resource_type"] for r in data}
    assert resource_types == {"CPU", "GPU", "TPU"}

    # Check first resource structure
    resource = data[0]
    required_fields = {
        "resource_type",
        "available_units",
        "total_units",
        "utilization_percent",
        "base_price_per_hour",
        "current_price_per_hour",
        "demand_multiplier",
        "region",
    }
    assert set(resource.keys()) == required_fields

    # Verify data types
    assert isinstance(resource["available_units"], int)
    assert isinstance(resource["total_units"], int)
    assert isinstance(resource["utilization_percent"], float)
    assert isinstance(resource["base_price_per_hour"], (int, float))
    assert isinstance(resource["current_price_per_hour"], (int, float))
    assert isinstance(resource["demand_multiplier"], (int, float))

    # Verify constraints
    assert 0 <= resource["available_units"] <= resource["total_units"]
    assert 0 <= resource["utilization_percent"] <= 100
    assert resource["base_price_per_hour"] > 0
    assert resource["current_price_per_hour"] > 0
    assert resource["demand_multiplier"] > 0


@pytest.mark.asyncio
async def test_get_resource_availability_filtered(client):
    """Test resource availability endpoint with resource type filter."""
    response = client.get(f"{BASE}/resources/availability?resource_type=GPU")

    assert response.status_code == 200
    data = response.json()

    # Should return only GPU
    assert len(data) == 1
    assert data[0]["resource_type"] == "GPU"


@pytest.mark.asyncio
async def test_get_resource_availability_different_region(client):
    """Test resource availability endpoint with different region."""
    response = client.get(f"{BASE}/resources/availability?region=us-west-2")

    assert response.status_code == 200
    data = response.json()

    # Should return data for all resources in specified region
    assert len(data) == 3
    for resource in data:
        assert resource["region"] == "us-west-2"
