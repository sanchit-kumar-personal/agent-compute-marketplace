from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracer(app_name: str = "agentcloud"):
    """Initialize OpenTelemetry tracer with OTLP exporter"""
    provider = TracerProvider(resource=Resource.create({"service.name": app_name}))

    # OTLP exporter - defaults to localhost:4317 for gRPC
    otlp_exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)
