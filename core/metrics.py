"""
Prometheus metrics instrumentation for the Agent Compute Marketplace.

This module sets up FastAPI instrumentation to expose metrics in Prometheus format
at the /metrics endpoint with optional authentication.
"""

from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram
from fastapi import Request, HTTPException, status
import os

# Custom metrics
quotes_total = Counter("agentcloud_quotes_total", "Total number of quotes created")

# Domain-specific metrics
negotiation_latency = Histogram(
    "agentcloud_negotiation_latency_seconds",
    "Time taken for negotiation rounds to complete",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)

payment_success = Counter(
    "agentcloud_payment_success_total",
    "Total number of successful payments",
    ["provider"],  # Label for payment provider (stripe, paypal, etc.)
)


def negotiation_latency_instrumentor(info):
    """Instrumentation function for tracking negotiation latency."""
    if info.request.url.path.startswith("/quotes") and info.method == "POST":
        # Use the actual request duration
        negotiation_latency.observe(info.modified_duration)


def payment_success_instrumentor(info):
    """Instrumentation function for tracking payment success."""
    if info.request.url.path.startswith("/quotes") and "payment" in str(
        info.request.url
    ):
        if info.response and info.response.status_code < 400:
            provider = info.request.headers.get("X-Payment-Provider", "unknown")
            payment_success.labels(provider=provider).inc()


def init_metrics(app):
    """
    Initialize Prometheus metrics instrumentation for the FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        Instrumentator instance
    """
    inst = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
    )

    # Add custom domain-specific metrics
    inst.add(negotiation_latency_instrumentor)
    inst.add(payment_success_instrumentor)

    # Expose metrics endpoint
    inst.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return inst


def add_metrics_auth_middleware(app):
    """
    Add middleware to protect the /metrics endpoint in production.
    For production use, set METRICS_AUTH_TOKEN environment variable.
    """

    @app.middleware("http")
    async def metrics_auth_middleware(request: Request, call_next):
        # Only protect metrics endpoint
        if request.url.path == "/metrics":
            # For development, allow all requests
            if os.getenv("ENVIRONMENT", "development") == "development":
                return await call_next(request)

            # In production, check for metrics auth header or VPN access
            auth_header = request.headers.get("X-Metrics-Auth")
            expected_token = os.getenv("METRICS_AUTH_TOKEN")

            if expected_token and auth_header == expected_token:
                return await call_next(request)

            # Allow internal network access (VPN/private networks)
            client_ip = request.client.host if request.client else None
            if client_ip and (
                client_ip.startswith("10.")
                or client_ip.startswith("192.168.")
                or client_ip.startswith("172.")
            ):
                return await call_next(request)

            # Deny access
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Metrics endpoint access denied",
            )

        return await call_next(request)
