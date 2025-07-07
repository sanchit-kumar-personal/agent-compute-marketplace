from fastapi import Request
import structlog
from core.logging import BusinessEvents


async def log_api_entry(request: Request, call_next):
    """Middleware to log API entries with request details"""
    # Get a fresh logger each time to ensure test configurations are respected
    log = structlog.get_logger(__name__)

    log.info(
        BusinessEvents.API_ENTRY,
        method=request.method,
        url=str(request.url),
        client_host=request.client.host if request.client else None,
        path_params=dict(request.path_params),
        query_params=dict(request.query_params),
    )
    response = await call_next(request)
    return response
