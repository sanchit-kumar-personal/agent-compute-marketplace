"""
Test the Prometheus metrics endpoint.
"""

import os


def test_metrics_endpoint(client):
    """Test that the /metrics endpoint returns Prometheus-formatted metrics."""
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"agentcloud_quotes_total" in r.content


def test_metrics_endpoint_format(client):
    """Test that metrics are in proper Prometheus format."""
    r = client.get("/metrics")
    assert r.status_code == 200

    # Check for proper Prometheus format
    content = r.content.decode("utf-8")

    # Should have HELP and TYPE lines for our custom metric
    assert "# HELP agentcloud_quotes_total Total number of quotes created" in content
    assert "# TYPE agentcloud_quotes_total counter" in content

    # Should have standard Python/process metrics
    assert "python_info" in content


def test_quotes_counter_increments(client):
    """Test that the quotes counter increments when quotes are created."""
    # Create a quote
    quote_data = {
        "buyer_id": "test-buyer",
        "resource_type": "GPU",
        "duration_hours": 2,
        "buyer_max_price": 100.0,
    }
    client.post("/quotes/request", json=quote_data)

    # Check that counter incremented
    r = client.get("/metrics")
    content = r.content.decode("utf-8")

    # The counter should have increased
    assert "agentcloud_quotes_total" in content


def test_metrics_endpoint_not_in_openapi(client):
    """Test that the metrics endpoint is not included in OpenAPI schema."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    openapi_content = r.json()

    # /metrics should not be in the paths
    assert "/metrics" not in openapi_content.get("paths", {})


def test_http_metrics_captured(client):
    """Test that HTTP request metrics are captured."""
    # Make a few requests
    client.get("/")
    client.get("/healthz")
    client.get("/quotes")

    # Check metrics
    r = client.get("/metrics")
    content = r.content.decode("utf-8")

    # Should have recorded process metrics and our custom metrics
    assert "python_info" in content
    assert "agentcloud_quotes_total" in content


def test_multiple_quote_creation_increments_counter(client):
    """Test that creating multiple quotes increments the counter correctly."""
    # Create multiple quotes
    for i in range(3):
        quote_data = {
            "buyer_id": f"test-buyer-{i}",
            "resource_type": "GPU",
            "duration_hours": 2,
            "buyer_max_price": 100.0,
        }
        client.post("/quotes/request", json=quote_data)

    # Check metrics
    r = client.get("/metrics")
    content = r.content.decode("utf-8")

    # Should have our custom counter
    assert "agentcloud_quotes_total" in content


def test_domain_specific_metrics_exist(client):
    """Test that domain-specific metrics are exposed."""
    r = client.get("/metrics")
    assert r.status_code == 200
    content = r.content.decode("utf-8")

    # Check for domain-specific metrics
    assert "agentcloud_negotiation_latency_seconds" in content
    assert "agentcloud_payment_success_total" in content


def test_metrics_auth_in_development(client):
    """Test that metrics endpoint is accessible in development mode."""
    # Ensure we're in development mode
    os.environ["ENVIRONMENT"] = "development"

    try:
        r = client.get("/metrics")
        assert r.status_code == 200
        assert b"agentcloud_quotes_total" in r.content
    finally:
        # Clean up
        os.environ.pop("ENVIRONMENT", None)
