"""
TrustHire AI — Consent router (/api/v1/consent)
"""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user
from ..middleware.audit import audit_log
from ..models import ConsentRecord, Candidate
from ..schemas import ConsentGrant, ConsentOut, MessageResponse
from ..services.compliance.consent import (
    CONSENT_DEFINITIONS,
    grant_consent,
    revoke_consent,
    get_active_consent,
)

logger = logging.getLogger(__name__)
consent_router = APIRouter(prefix="/candidates/{candidate_id}/consent", tags=["consent"])


def _assert_candidate_access(candidate: Candidate | None, current_user) -> None:
    if not candidate or candidate.deleted_at or candidate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found")


@consent_router.get("/", response_model=list[ConsentOut])
async def list_consents(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _assert_candidate_access(candidate, current_user)

    result = await db.execute(
        select(ConsentRecord).where(ConsentRecord.candidate_id == candidate_id)
        .order_by(ConsentRecord.created_at.desc())
    )
    return [ConsentOut.model_validate(r) for r in result.scalars().all()]


@consent_router.post("", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
async def grant_candidate_consent(
    candidate_id: uuid.UUID,
    payload: ConsentGrant,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _assert_candidate_access(candidate, current_user)

    if payload.consent_type not in CONSENT_DEFINITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown consent type. Valid types: {list(CONSENT_DEFINITIONS.keys())}",
        )

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    record = await grant_consent(
        candidate_id=str(candidate_id),
        consent_type=payload.consent_type,
        ip_address=ip,
        user_agent=ua,
        version=payload.version,
    )
    return ConsentOut.model_validate(record)


@consent_router.delete("/{consent_type}", response_model=MessageResponse)
async def revoke_candidate_consent(
    candidate_id: uuid.UUID,
    consent_type: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _assert_candidate_access(candidate, current_user)

    record = await get_active_consent(str(candidate_id), consent_type)
    if not record:
        raise HTTPException(status_code=404, detail=f"No active consent found for '{consent_type}'")

    await revoke_consent(str(candidate_id), consent_type)
    return MessageResponse(message=f"Consent '{consent_type}' revoked successfully")


# ─────────────────────────────────────────────────────────────────────────────
# FRAUD FLAGS ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from datetime import datetime
from ..models import FraudFlag, User
from ..schemas import FraudFlagOut, FraudFlagReview

fraud_router = APIRouter(prefix="/fraud-flags", tags=["fraud"])


@fraud_router.get("/candidates/{candidate_id}", response_model=list[FraudFlagOut])
async def get_fraud_flags(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _assert_candidate_access(candidate, current_user)

    result = await db.execute(
        select(FraudFlag)
        .where(FraudFlag.candidate_id == candidate_id)
        .order_by(FraudFlag.created_at.desc())
    )
    return [FraudFlagOut.model_validate(f) for f in result.scalars().all()]


@fraud_router.patch("/{flag_id}/review", response_model=FraudFlagOut)
async def review_fraud_flag(
    flag_id: uuid.UUID,
    payload: FraudFlagReview,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    flag = await db.get(FraudFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Fraud flag not found")

    # Ensure reviewer belongs to same org as candidate
    candidate = await db.get(Candidate, flag.candidate_id)
    if not candidate or candidate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Fraud flag not found")

    flag.reviewed_by = current_user.id
    flag.reviewed_at = datetime.utcnow()
    flag.review_outcome = payload.outcome
    flag.requires_review = False
    await db.commit()
    await db.refresh(flag)

    await audit_log(
        action="fraud_flag.reviewed",
        candidate_id=str(flag.candidate_id),
        user_id=str(current_user.id),
        new_values={"flag_id": str(flag_id), "outcome": payload.outcome},
    )

    return FraudFlagOut.model_validate(flag)


# ─────────────────────────────────────────────────────────────────────────────
# REPORTS ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from ..schemas import RiskScoreOut
from ..models import RiskScore
from sqlalchemy import select as _select

reports_router = APIRouter(prefix="/candidates/{candidate_id}", tags=["reports"])


@reports_router.get("/risk-score", response_model=RiskScoreOut)
async def get_risk_score(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _assert_candidate_access(candidate, current_user)

    result = await db.execute(
        _select(RiskScore)
        .where(RiskScore.candidate_id == candidate_id)
        .order_by(RiskScore.calculated_at.desc())
        .limit(1)
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="No risk score calculated yet")
    return RiskScoreOut.model_validate(score)


@reports_router.get("/report/pdf")
async def get_report_pdf_url(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _assert_candidate_access(candidate, current_user)

    from services.storage.minio_client import get_signed_url
    from services.reporting.generator import generate_pdf_report

    # Generate fresh report
    storage_path = await generate_pdf_report(str(candidate_id))
    url = await get_signed_url(storage_path, expires_minutes=30)

    await audit_log(
        action="report.downloaded",
        candidate_id=str(candidate_id),
        user_id=str(current_user.id),
    )

    return {"url": url, "expires_in_minutes": 30}


# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from ..models import AuditLog
from ..schemas import AuditLogOut

compliance_router = APIRouter(prefix="/compliance", tags=["compliance"])


@compliance_router.get("/audit-logs", response_model=list[AuditLogOut])
async def get_audit_logs(
    page: int = 1,
    limit: int = 50,
    candidate_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from middleware.auth import require_roles
    from sqlalchemy import select as _sel

    if current_user.role not in ("org_admin", "compliance_reviewer", "super_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    q = _sel(AuditLog).where(AuditLog.organization_id == current_user.organization_id)
    if candidate_id:
        q = q.where(AuditLog.candidate_id == candidate_id)

    q = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    return [AuditLogOut.model_validate(r) for r in result.scalars().all()]


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from ..models import Notification
from ..schemas import NotificationOut

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notifications_router.get("", response_model=list[NotificationOut])
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    return [NotificationOut.model_validate(n) for n in result.scalars().all()]


@notifications_router.patch("/{notif_id}/read", response_model=MessageResponse)
async def mark_notification_read(
    notif_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    notif = await db.get(Notification, notif_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    notif.read_at = datetime.utcnow()
    await db.commit()
    return MessageResponse(message="Marked as read")


@notifications_router.post("/read-all", response_model=MessageResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True, read_at=datetime.utcnow())
    )
    await db.commit()
    return MessageResponse(message="All notifications marked as read")


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ROUTER
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy import func

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/usage")
async def get_usage_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from models import VerificationRequest
    from sqlalchemy import select as _sel

    org_id = current_user.organization_id

    total_cands = await db.scalar(
        _sel(func.count(Candidate.id)).where(
            Candidate.organization_id == org_id,
            Candidate.deleted_at.is_(None),
        )
    )
    running = await db.scalar(
        _sel(func.count(VerificationRequest.id)).where(
            VerificationRequest.organization_id == org_id,
            VerificationRequest.status == "running",
        )
    )
    completed_today_ts = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = await db.scalar(
        _sel(func.count(VerificationRequest.id)).where(
            VerificationRequest.organization_id == org_id,
            VerificationRequest.status == "completed",
            VerificationRequest.completed_at >= completed_today_ts,
        )
    )
    unreviewed_flags = await db.scalar(
        _sel(func.count(FraudFlag.id)).where(
            FraudFlag.candidate_id.in_(
                _sel(Candidate.id).where(Candidate.organization_id == org_id)
            ),
            FraudFlag.reviewed_at.is_(None),
        )
    )

    return {
        "total_candidates": total_cands or 0,
        "running_verifications": running or 0,
        "completed_today": completed_today or 0,
        "unreviewed_fraud_flags": unreviewed_flags or 0,
    }


@admin_router.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
