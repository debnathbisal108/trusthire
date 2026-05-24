"""
TrustHire AI — Redis-backed sliding window rate limiting.
"""

import time
import logging

import redis.asyncio as aioredis
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None

# (requests, window_seconds)
_ROUTE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth":        (10, 60),
    "/voice":              (30, 60),
    "default":             (120, 60),
}


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _resolve_limit(path: str) -> tuple[int, int]:
    for prefix, limits in _ROUTE_LIMITS.items():
        if prefix != "default" and path.startswith(prefix):
            return limits
    return _ROUTE_LIMITS["default"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = (request.client.host if request.client else "unknown")
        path = request.url.path
        limit, window = _resolve_limit(path)

        # Bucket key — per IP + route-group
        bucket = path.split("/")[3] if len(path.split("/")) > 3 else "root"
        key = f"rl:{ip}:{bucket}"
        now = time.time()

        try:
            r = _get_redis()
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()
            count = results[2]
        except Exception as exc:
            logger.warning("Rate limit Redis error: %s — allowing request", exc)
            return await call_next(request)

        if count > limit:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "code": "RATE_LIMITED"},
                headers={"Retry-After": str(window)},
            )

        return await call_next(request)
