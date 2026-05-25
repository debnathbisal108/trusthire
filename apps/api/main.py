"""
TrustHire AI — FastAPI application entry point.
Voice call feature removed. Uses free cloud LLMs (Gemini/Groq/Mistral/Cohere).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import settings
from .database import engine, Base
from .middleware.audit import AuditMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routers.candidates import router as candidates_router
from .routers.verifications import router as verifications_router
from .routers.misc import (
    consent_router,
    fraud_router,
    reports_router,
    compliance_router,
    notifications_router,
    admin_router,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(
        "TrustHire AI started — env=%s llm=%s",
        settings.environment,
        settings.llm_provider,
    )
    yield
    await engine.dispose()
    logger.info("TrustHire AI shut down")


app = FastAPI(
    title="TrustHire AI API",
    description="AI-powered background verification — free cloud LLMs",
    version="1.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url="/api/redoc" if settings.environment != "production" else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(candidates_router,    prefix=PREFIX)
app.include_router(verifications_router, prefix=PREFIX)
app.include_router(consent_router,       prefix=PREFIX)
app.include_router(fraud_router,         prefix=PREFIX)
app.include_router(reports_router,       prefix=PREFIX)
app.include_router(compliance_router,    prefix=PREFIX)
app.include_router(notifications_router, prefix=PREFIX)
app.include_router(admin_router,         prefix=PREFIX)


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request validation failed",
            "code": "VALIDATION_ERROR",
            "details": exc.errors(),
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "")
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )


# ── System endpoints ──────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    from services.ai.model_router import get_provider_info
    return {
        "status": "ok",
        "version": "1.1.0",
        "environment": settings.environment,
        "llm": get_provider_info(),
    }


@app.get("/metrics", include_in_schema=False)
async def metrics():
    from fastapi.responses import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
