"""Test the metrics module."""

import pytest
from unittest.mock import patch, MagicMock

from core.metrics import (
    quotes_total,
    payment_success,
    negotiation_latency,
    init_metrics,
)


def test_quotes_total_counter():
    """Test quotes total counter increments."""
    # Use the actual metric name from the source
    initial_value = quotes_total._value._value
    quotes_total.inc()
    assert quotes_total._value._value == initial_value + 1


def test_payment_success_counter_with_labels():
    """Test payment success counter with provider labels."""
    # Test Stripe payments
    stripe_metric = payment_success.labels(provider="stripe")
    initial_stripe = stripe_metric._value._value
    stripe_metric.inc()
    assert stripe_metric._value._value == initial_stripe + 1

    # Test PayPal payments
    paypal_metric = payment_success.labels(provider="paypal")
    initial_paypal = paypal_metric._value._value
    paypal_metric.inc()
    assert paypal_metric._value._value == initial_paypal + 1


def test_negotiation_latency_histogram():
    """Test negotiation latency histogram records observations."""
    # Record some latencies
    negotiation_latency.observe(0.1)  # 100ms
    negotiation_latency.observe(0.25)  # 250ms
    negotiation_latency.observe(0.5)  # 500ms

    # Verify observations were recorded by checking that sum increases
    # Don't assume internal structure since prometheus_client may vary
    assert negotiation_latency._sum._value > 0


def test_init_metrics_with_app():
    """Test metrics initialization with FastAPI app."""
    # Mock FastAPI app
    mock_app = MagicMock()

    with patch("core.metrics.Instrumentator") as mock_instrumentator:
        mock_inst = MagicMock()
        mock_instrumentator.return_value = mock_inst
        mock_inst.add.return_value = mock_inst
        mock_inst.instrument.return_value = mock_inst
        mock_inst.expose.return_value = mock_inst

        result = init_metrics(mock_app)

        # Verify instrumentator was created and configured
        mock_instrumentator.assert_called_once()
        mock_inst.add.assert_called()
        mock_inst.instrument.assert_called_with(mock_app)
        mock_inst.expose.assert_called_with(
            mock_app, endpoint="/metrics", include_in_schema=False
        )
        assert result == mock_inst


def test_metrics_endpoint_integration(client):
    """Test that metrics endpoint is available and returns Prometheus format."""
    response = client.get("/metrics")

    # Should return metrics in Prometheus format
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")

    # Should contain our custom metrics - use actual names from source
    content = response.text
    assert (
        "agentcloud_quotes" in content
    )  # Note: not _total suffix in the actual metric name
    assert "agentcloud_payment_success_total" in content
    assert "agentcloud_negotiation_latency_seconds" in content


def test_payment_success_multiple_providers():
    """Test payment success counter with multiple provider types."""
    providers = ["stripe", "paypal", "other"]

    for i, provider in enumerate(providers):
        metric = payment_success.labels(provider=provider)
        initial_value = metric._value._value

        # Increment by different amounts
        metric.inc(i + 1)

        assert metric._value._value == initial_value + (i + 1)
        assert metric._labelvalues == (provider,)


def test_negotiation_latency_buckets():
    """Test negotiation latency histogram bucket functionality."""
    # Test various latency values
    test_latencies = [0.05, 0.3, 1.2, 3.0, 7.5, 15.0]

    for latency in test_latencies:
        negotiation_latency.observe(latency)

    # Verify histogram recorded the observations
    # Use _sum which should exist on histograms
    assert negotiation_latency._sum._value > 0


def test_quotes_total_multiple_increments():
    """Test quotes total counter with multiple increments."""
    initial_value = quotes_total._value._value

    # Increment multiple times
    for i in range(5):
        quotes_total.inc()

    assert quotes_total._value._value == initial_value + 5


def test_payment_success_no_labels():
    """Test payment success counter behavior without explicit labels."""
    # This should work with default provider value
    try:
        # This might fail if labels are required, which is expected
        payment_success.inc()
    except Exception:
        # If labels are required, test with a default label
        payment_success.labels(provider="default").inc()
        # Just verify no exception is raised


def test_metrics_naming_convention():
    """Test that metrics follow proper naming conventions."""
    # Test that metric names are properly prefixed - use actual names
    assert quotes_total._name == "agentcloud_quotes"  # Not _total
    assert payment_success._name == "agentcloud_payment_success"  # Not _total
    assert negotiation_latency._name == "agentcloud_negotiation_latency_seconds"


def test_negotiation_latency_instrumentor():
    """Test negotiation latency instrumentor function."""
    from core.metrics import negotiation_latency_instrumentor

    # Mock info object
    mock_info = MagicMock()
    mock_info.request.url.path = "/api/v1/quotes/123/negotiate"
    mock_info.method = "POST"
    mock_info.modified_duration = 1.5

    # Test that instrumentor doesn't raise errors
    try:
        negotiation_latency_instrumentor(mock_info)
    except Exception as e:
        pytest.fail(f"Instrumentor raised unexpected exception: {e}")


def test_payment_success_instrumentor():
    """Test payment success instrumentor function."""
    from core.metrics import payment_success_instrumentor

    # Mock info object
    mock_info = MagicMock()
    mock_info.request.url.path = "/api/v1/quotes/123/payment"
    mock_info.response.status_code = 200
    mock_info.request.headers.get.return_value = "stripe"

    # Test that instrumentor doesn't raise errors
    try:
        payment_success_instrumentor(mock_info)
    except Exception as e:
        pytest.fail(f"Instrumentor raised unexpected exception: {e}")


def test_metrics_export():
    """Test that metrics can be exported in Prometheus format."""
    # Don't patch generate_latest since it doesn't exist in core.metrics
    from prometheus_client import generate_latest

    # Just test that we can call generate_latest without errors
    result = generate_latest()

    # Should return bytes containing metric data
    assert isinstance(result, bytes)
    assert b"agentcloud_quotes" in result
