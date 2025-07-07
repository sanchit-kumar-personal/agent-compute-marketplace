import sys
import tempfile
import os
import structlog
from core.logging import BusinessEvents


def capture_log_output(func):
    """Helper to capture log output"""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        # Save original stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            # Redirect both stdout and stderr to the temp file
            sys.stdout = tmp
            sys.stderr = tmp
            # Execute the logging function
            func()
            # Flush the buffers
            tmp.flush()
            # Read the file
            with open(tmp.name, "r") as f:
                output = f.read()
            # Extract the JSON line (last line that starts with {"
            for line in output.splitlines():
                if line.startswith("{"):
                    return line
            return ""
        finally:
            # Restore stdout and stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            # Clean up the temp file
            os.unlink(tmp.name)


class _TestLogger:
    def __init__(self):
        self.output = []

    def __call__(self, logger, method_name, event_dict):
        """Process log events and store them for test assertions"""
        self.output.append(event_dict.copy())
        return event_dict


def test_structlog_json():
    # Create a test logger
    test_logger = _TestLogger()

    # Configure structlog with our test logger
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            test_logger,  # Add our test logger
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Get a logger and log a message
    log = structlog.get_logger("test")
    log.bind(foo="bar").info("hello world")

    # Get the last log entry
    assert len(test_logger.output) > 0
    log_dict = test_logger.output[-1]

    assert log_dict["foo"] == "bar"
    assert log_dict["event"] == "hello world"
    assert "timestamp" in log_dict
    assert log_dict["level"] == "info"


def test_payment_log_format():
    # Create a test logger
    test_logger = _TestLogger()

    # Configure structlog with our test logger
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            test_logger,  # Add our test logger
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Get a logger and log a message
    log = structlog.get_logger("test.payments")
    log.bind(quote_id="qt_123", amount_usd=99.99, provider_id="pi_456").info(
        "payment.captured"
    )

    # Get the last log entry
    assert len(test_logger.output) > 0
    log_dict = test_logger.output[-1]

    assert log_dict["quote_id"] == "qt_123"
    assert log_dict["amount_usd"] == 99.99
    assert log_dict["provider_id"] == "pi_456"
    assert log_dict["event"] == "payment.captured"
    assert "timestamp" in log_dict
    assert log_dict["level"] == "info"


def test_api_request_logging(client):
    """Test that API requests are properly logged with structured data."""
    # Create a test logger
    test_logger = _TestLogger()

    # Clear structlog's cache to ensure our test configuration is used
    structlog.reset_defaults()

    # Also clear the logger cache to ensure cached loggers are reconfigured
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            test_logger,  # Add our test logger
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,  # Don't cache to ensure fresh config
    )

    # Make an API request
    response = client.post(
        "/quotes/request",
        json={
            "buyer_id": "test_buyer",
            "resource_type": "GPU",
            "duration_hours": 4,
            "buyer_max_price": 10.0,
        },
    )
    assert response.status_code == 201

    # Find the API request log
    api_logs = [
        log
        for log in test_logger.output
        if log.get("event") == BusinessEvents.API_ENTRY
    ]
    assert len(api_logs) > 0

    log_entry = api_logs[0]
    assert log_entry["method"] == "POST"
    assert "/quotes/request" in log_entry["url"]
    assert log_entry["level"] == "info"
    assert "timestamp" in log_entry

    # Find the quote creation log
    quote_logs = [
        log
        for log in test_logger.output
        if log.get("event") == BusinessEvents.QUOTE_CREATED
    ]
    assert len(quote_logs) > 0

    quote_log = quote_logs[0]
    assert quote_log["buyer_id"] == "test_buyer"
    assert quote_log["resource_type"] == "GPU"
    assert quote_log["duration_hours"] == 4
    assert quote_log["buyer_max_price"] == 10.0
    assert "quote_id" in quote_log
