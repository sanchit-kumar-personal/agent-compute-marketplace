import logging
import sys
import structlog
import os
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Global variable to store test output
test_output = []


def get_log_level():
    """Get log level from environment or default to INFO"""
    return os.getenv("LOG_LEVEL", "INFO").upper()


def get_log_renderer():
    """Get log renderer based on environment"""
    env = os.getenv("ENVIRONMENT", "development")
    # Use JSON format for tests and production
    if env in ["test", "production"]:
        return structlog.processors.JSONRenderer()
    # Pretty printing for local development
    return structlog.dev.ConsoleRenderer(colors=True, sort_keys=False)


def test_output_processor(logger, method_name, event_dict):
    """Custom processor that stores output for test assertions"""
    env = os.getenv("ENVIRONMENT", "development")
    if env == "test":
        # Store the event dict for test assertions
        test_output.append(event_dict.copy())
    return event_dict


def configure_logging():
    """Set up structlog + OTEL context injection."""
    # Configure shared processors for all loggers
    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.ExceptionPrettyPrinter(),
    ]

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            test_output_processor,  # Add our custom processor before rendering
            get_log_renderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set up stdlib logging
    env = os.getenv("ENVIRONMENT", "development")
    if env == "test":
        # In test mode, write to stdout for easier capture
        handler = logging.StreamHandler(sys.stdout)
    else:
        # In other modes, write to stderr (default)
        handler = logging.StreamHandler()

    # Configure the handler
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]  # Replace any existing handlers
    root_logger.setLevel(get_log_level())

    # Silence Uvicorn noise but keep access logs routed through structlog
    logging.getLogger("uvicorn.error").handlers.clear()
    logging.getLogger("uvicorn.access").handlers.clear()

    # Initialize OpenTelemetry logging instrumentation AFTER configuring logging
    LoggingInstrumentor().instrument(set_logging_format=False)


# Business Event Log Names
class BusinessEvents:
    """Standard names for business event logs"""

    API_ENTRY = "api.request"
    QUOTE_CREATED = "quote.created"
    NEGOTIATION_TURN = "negotiation.turn"
    QUOTE_ACCEPTED = "quote.accepted"
    QUOTE_REJECTED = "quote.rejected"
    PAYMENT_ATTEMPT = "payment.attempt"
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILURE = "payment.failure"


# Configure logging when module is imported
configure_logging()
