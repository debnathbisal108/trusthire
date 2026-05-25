"""
TrustHire AI — Audit logging middleware.
Every API request is logged; audit_log() helper for business events.
"""

import uuid
import time
import logging
from datetime import datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..tests.database import AsyncSessionLocal
from ..tests.models import AuditLog

logger = logging.getLogger("audit")

_SKIP_PATHS = {"/health", "/metrics", "/api/docs", "/api/redoc", "/openapi.json"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = round((time.monotonic() - start) * 1000)

        user_id = getattr(request.state, "user_id", None)
        org_id = getattr(request.state, "org_id", None)

        logger.info(
            "api.request path=%s method=%s status=%s duration_ms=%s user=%s request_id=%s",
            request.url.path,
            request.method,
            response.status_code,
            elapsed_ms,
            user_id,
            request_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response


async def audit_log(
    *,
    action: str,
    candidate_id: str | None = None,
    user_id: str | None = None,
    organization_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Write an immutable audit log entry.
    Uses its own DB session so it never rolls back with the parent transaction.
    """
    async with AsyncSessionLocal() as session:
        try:
            entry = AuditLog(
                organization_id=uuid.UUID(organization_id) if organization_id else None,
                user_id=uuid.UUID(user_id) if user_id else None,
                candidate_id=uuid.UUID(candidate_id) if candidate_id else None,
                action=action,
                entity_type=entity_type,
                entity_id=uuid.UUID(entity_id) if entity_id else None,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(entry)
            await session.commit()
        except Exception as exc:
            logger.error("audit_log write failed: %s", exc)
