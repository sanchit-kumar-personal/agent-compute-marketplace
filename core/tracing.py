import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log = structlog.get_logger(__name__)


def init_tracer(app_name: str = "agentcloud"):
    """Initialize OpenTelemetry tracer with OTLP exporter"""
    provider = TracerProvider(resource=Resource.create({"service.name": app_name}))

    # Attempt to create OTLP exporter (defaults to localhost:4317). If this
    # fails (e.g. during local tests without Jaeger), gracefully fall back to a
    # no-op console exporter so the tracer still works but doesn't raise
    # background logging errors.
    # Allow disabling tracing via environment variable (useful in tests)
    import os

    if os.getenv("DISABLE_TRACING", "").lower() in {"1", "true", "yes"}:
        # Use a no-op console exporter to avoid background errors
        otlp_exporter = ConsoleSpanExporter()
    else:
        try:
            otlp_exporter = OTLPSpanExporter()
        except Exception as exc:  # pragma: no cover – only hit when Jaeger absent
            log.warning("OTLP exporter unavailable, tracing disabled", error=str(exc))
            otlp_exporter = ConsoleSpanExporter()  # writes spans to stdout

    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)
