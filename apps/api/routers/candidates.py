"""
TrustHire AI — /api/v1/candidates router.
"""

import hashlib
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user, require_roles
from ..middleware.audit import audit_log
from ..models import Candidate, Document, FraudFlag
from schemas import (
    CandidateListItem,
    CandidateListResponse,
    CandidateOut,
    MessageResponse,
)
from security import encrypt_pii, decrypt_pii
from services.storage.minio_client import upload_file, get_signed_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["candidates"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "image/webp",
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ─────────────────────────────────────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=CandidateListResponse)
async def list_candidates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    risk_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    base_q = select(Candidate).where(
        Candidate.organization_id == current_user.organization_id,
        Candidate.deleted_at.is_(None),
    )

    if status_filter:
        base_q = base_q.where(Candidate.status == status_filter)
    if risk_level:
        base_q = base_q.where(Candidate.risk_level == risk_level)
    if search:
        base_q = base_q.where(Candidate.full_name.ilike(f"%{search}%"))

    total_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(
        base_q.order_by(Candidate.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    candidates = result.scalars().all()

    # Fetch fraud flag counts
    items = []
    for c in candidates:
        ff_result = await db.execute(
            select(func.count()).where(FraudFlag.candidate_id == c.id)
        )
        ff_count = ff_result.scalar_one()
        items.append(
            CandidateListItem(
                id=c.id,
                full_name=c.full_name,
                status=c.status,
                risk_score=c.risk_score,
                risk_level=c.risk_level,
                fraud_flag_count=ff_count,
                created_at=c.created_at,
            )
        )

    return CandidateListResponse(
        data=items,
        meta={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max(1, -(-total // limit)),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREATE (with file upload)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    full_name: str = Form(..., min_length=2, max_length=255),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("recruiter", "org_admin", "super_admin")),
):
    # ── File validation ──────────────────────────────────────────────────────
    content = await resume.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit",
        )

    # Detect MIME type from content (not filename — avoids extension spoofing)
    try:
        import magic as libmagic
        mime = libmagic.from_buffer(content, mime=True)
    except Exception:
        mime = resume.content_type or "application/octet-stream"

    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime}. Allowed: PDF, DOCX, PNG, JPEG",
        )

    checksum = hashlib.sha256(content).hexdigest()

    # ── Create candidate record ──────────────────────────────────────────────
    candidate = Candidate(
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        full_name=full_name.strip(),
        email=encrypt_pii(email) if email else None,
        phone=encrypt_pii(phone) if phone else None,
        linkedin_url=linkedin_url,
        status="parsing",
    )
    db.add(candidate)
    await db.flush()  # Get the UUID without committing

    # ── Upload to MinIO ──────────────────────────────────────────────────────
    safe_filename = resume.filename or "resume"
    storage_path = f"resumes/{candidate.id}/{safe_filename}"
    await upload_file(content, storage_path, mime)

    # ── Create document record ───────────────────────────────────────────────
    doc = Document(
        candidate_id=candidate.id,
        file_name=safe_filename,
        file_size=len(content),
        mime_type=mime,
        storage_path=storage_path,
        checksum=checksum,
        doc_type="resume",
        scan_status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(candidate)

    # ── Enqueue parsing task ─────────────────────────────────────────────────
    from tasks.celery_app import parse_resume_task
    parse_resume_task.delay(str(candidate.id), str(doc.id))

    # ── Audit ────────────────────────────────────────────────────────────────
    await audit_log(
        action="candidate.create",
        candidate_id=str(candidate.id),
        user_id=str(current_user.id),
        organization_id=str(current_user.organization_id),
        new_values={"full_name": full_name, "file": safe_filename},
    )

    return CandidateOut.model_validate(candidate)


# ─────────────────────────────────────────────────────────────────────────────
# GET ONE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _check_access(candidate, current_user)
    return CandidateOut.model_validate(candidate)


# ─────────────────────────────────────────────────────────────────────────────
# SOFT DELETE
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{candidate_id}", response_model=MessageResponse)
async def delete_candidate(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("org_admin", "super_admin")),
):
    candidate = await db.get(Candidate, candidate_id)
    _check_access(candidate, current_user)

    candidate.deleted_at = datetime.utcnow()
    candidate.status = "deleted"
    await db.commit()

    await audit_log(
        action="candidate.delete",
        candidate_id=str(candidate_id),
        user_id=str(current_user.id),
    )
    return MessageResponse(message="Candidate soft-deleted successfully")


# ─────────────────────────────────────────────────────────────────────────────
# GET DOCUMENT DOWNLOAD URL
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{candidate_id}/documents/{doc_id}/url")
async def get_document_url(
    candidate_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    candidate = await db.get(Candidate, candidate_id)
    _check_access(candidate, current_user)

    doc = await db.get(Document, doc_id)
    if not doc or doc.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="Document not found")

    url = await get_signed_url(doc.storage_path, expires_minutes=15)
    return {"url": url, "expires_in_minutes": 15}


# ─────────────────────────────────────────────────────────────────────────────
# GDPR ERASURE
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{candidate_id}/gdpr/erase", response_model=MessageResponse)
async def gdpr_erase(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("org_admin", "compliance_reviewer", "super_admin")),
):
    """GDPR Article 17 — right to erasure."""
    from sqlalchemy import select as _sel
    from models import Document, ConsentRecord, VerificationRequest
    from services.storage.minio_client import delete_file

    candidate = await db.get(Candidate, candidate_id)
    _check_access(candidate, current_user)

    # Delete documents from MinIO
    doc_result = await db.execute(_sel(Document).where(Document.candidate_id == candidate_id))
    for doc in doc_result.scalars().all():
        try:
            await delete_file(doc.storage_path)
        except Exception:
            pass
        doc.storage_path = "[ERASED]"
        doc.file_name = "[ERASED]"

    # Revoke all consents
    from sqlalchemy import update
    await db.execute(
        update(ConsentRecord)
        .where(ConsentRecord.candidate_id == candidate_id)
        .values(status="revoked", revoked_at=datetime.utcnow())
    )

    # Cancel verifications
    from tasks.celery_app import celery_app
    vr_result = await db.execute(
        _sel(VerificationRequest).where(
            VerificationRequest.candidate_id == candidate_id,
            VerificationRequest.status.in_(["pending", "running"]),
        )
    )
    for vr in vr_result.scalars().all():
        if vr.celery_task_id:
            try:
                celery_app.control.revoke(vr.celery_task_id, terminate=True)
            except Exception:
                pass
        vr.status = "cancelled"

    # Anonymise candidate
    candidate.full_name = "[ERASED]"
    candidate.email = None
    candidate.phone = None
    candidate.raw_text = None
    candidate.parsed_data = None
    candidate.linkedin_url = None
    candidate.deleted_at = datetime.utcnow()

    await db.commit()

    await audit_log(
        action="gdpr.erasure_completed",
        candidate_id=str(candidate_id),
        user_id=str(current_user.id),
        new_values={"requested_by": str(current_user.id), "completed_at": datetime.utcnow().isoformat()},
    )

    return MessageResponse(message="Candidate data erased under GDPR Article 17")


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def _check_access(candidate: Candidate | None, current_user) -> None:
    if not candidate or candidate.deleted_at or candidate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found")
