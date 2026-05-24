"""
TrustHire AI — /api/v1/verifications router.
"""

import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import get_current_user, require_roles
from middleware.audit import audit_log
from models import Candidate, VerificationRequest
from schemas import MessageResponse, VerificationCreate, VerificationOut
from services.compliance.consent import verify_consents_for_verification, ConsentMissingError, ConsentExpiredError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/verifications", tags=["verifications"])


@router.post("/", response_model=VerificationOut, status_code=status.HTTP_201_CREATED)
async def create_verification(
    payload: VerificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("recruiter", "org_admin", "super_admin")),
):
    # ── Candidate ownership check ──
    candidate = await db.get(Candidate, payload.candidate_id)
    if not candidate or candidate.deleted_at or candidate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if candidate.status == "parsing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resume is still being parsed. Please wait before starting verification.",
        )

    # ── Consent gate ──────────────────────────────────────────────────────────
    try:
        await verify_consents_for_verification(str(payload.candidate_id), payload.config.model_dump())
    except ConsentMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": str(exc), "code": "CONSENT_MISSING"},
        )
    except ConsentExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": str(exc), "code": "CONSENT_EXPIRED"},
        )

    # ── Create verification record ────────────────────────────────────────────
    verif = VerificationRequest(
        organization_id=current_user.organization_id,
        candidate_id=payload.candidate_id,
        requested_by=current_user.id,
        status="pending",
        config=payload.config.model_dump(),
    )
    db.add(verif)
    await db.commit()
    await db.refresh(verif)

    # ── Enqueue Celery task ───────────────────────────────────────────────────
    from tasks.celery_app import run_verification_task
    task = run_verification_task.delay(str(verif.id))

    verif.celery_task_id = task.id
    verif.status = "running"
    verif.started_at = datetime.utcnow()
    await db.commit()
    await db.refresh(verif)

    await audit_log(
        action="verification.start",
        candidate_id=str(payload.candidate_id),
        user_id=str(current_user.id),
        organization_id=str(current_user.organization_id),
        new_values={"verification_id": str(verif.id), "config": payload.config.model_dump()},
    )

    return VerificationOut.model_validate(verif)


@router.get("/{verif_id}", response_model=VerificationOut)
async def get_verification(
    verif_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    verif = await db.get(VerificationRequest, verif_id)
    if not verif or verif.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Verification not found")
    return VerificationOut.model_validate(verif)


@router.post("/{verif_id}/cancel", response_model=MessageResponse)
async def cancel_verification(
    verif_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("recruiter", "org_admin", "super_admin")),
):
    verif = await db.get(VerificationRequest, verif_id)
    if not verif or verif.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Verification not found")

    if verif.status not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel verification in status '{verif.status}'",
        )

    if verif.celery_task_id:
        try:
            from tasks.celery_app import celery_app
            celery_app.control.revoke(verif.celery_task_id, terminate=True)
        except Exception as exc:
            logger.warning("Could not revoke Celery task %s: %s", verif.celery_task_id, exc)

    verif.status = "cancelled"
    await db.commit()

    await audit_log(
        action="verification.cancel",
        candidate_id=str(verif.candidate_id),
        user_id=str(current_user.id),
        new_values={"verification_id": str(verif_id)},
    )

    return MessageResponse(message="Verification cancelled")


@router.post("/{verif_id}/retry", response_model=VerificationOut)
async def retry_verification(
    verif_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("recruiter", "org_admin", "super_admin")),
):
    verif = await db.get(VerificationRequest, verif_id)
    if not verif or verif.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Verification not found")

    if verif.status not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Can only retry failed or cancelled verifications, not '{verif.status}'",
        )

    from tasks.celery_app import run_verification_task
    task = run_verification_task.delay(str(verif.id))

    verif.celery_task_id = task.id
    verif.status = "running"
    verif.started_at = datetime.utcnow()
    verif.completed_at = None
    await db.commit()
    await db.refresh(verif)

    await audit_log(
        action="verification.retry",
        candidate_id=str(verif.candidate_id),
        user_id=str(current_user.id),
        new_values={"verification_id": str(verif_id)},
    )

    return VerificationOut.model_validate(verif)
