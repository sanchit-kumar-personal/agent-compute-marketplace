"""
Audit Middleware Module

This module provides middleware for logging all API requests that result in 2xx responses.
Every quote/payment action is recorded in the audit_logs table.
"""

from collections.abc import Callable

import structlog
from fastapi import Request, Response
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from db import models
from db.models import AuditAction

log = structlog.get_logger(__name__)


def determine_action(request: Request, response: Response) -> AuditAction:
    """Determine the audit action based on the request path."""
    path = request.url.path
    if "negotiate" in path:
        return AuditAction.negotiation_turn
    elif "payment" in path:
        return AuditAction.payment_succeeded
    else:
        return AuditAction.quote_created


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to audit all /api requests with 2xx responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Process the request
        response = await call_next(request)

        # Only log for 2xx responses from our API prefix
        if (
            request.url.path.startswith("/api")
            and 200 <= response.status_code < 300
            and "webhook" not in request.url.path  # Skip webhook logging for now
        ):
            try:
                # grab the route's session if it exists, else skip audit
                db: Session | None = getattr(request.state, "db", None)
                if not db:
                    return response

                # log only 2xx/3xx responses
                if 200 <= response.status_code < 400 and request.url.path.startswith(
                    "/api"
                ):
                    db.add(
                        models.AuditLog(
                            quote_id=getattr(request.state, "quote_id", None),
                            action=determine_action(
                                request, response
                            ),  # helper keeps previous
                            payload={
                                "method": request.method,
                                "path": str(request.url.path),
                                "status": response.status_code,
                                "body": (await request.body()).decode()[:500],
                            },
                        )
                    )
                    db.commit()
            except Exception as e:
                log.error("audit.session_failed", path=request.url.path, error=str(e))

        return response
