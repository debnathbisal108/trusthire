"""
TrustHire AI — Pydantic schemas for all API request/response models.
"""

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field, UUID4


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    userId: Optional[str] = None
    organizationId: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None


class UserOut(BaseModel):
    id: UUID4
    email: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    role: str
    organization_id: Optional[UUID4]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZATION
# ─────────────────────────────────────────────────────────────────────────────

class OrganizationOut(BaseModel):
    id: UUID4
    name: str
    slug: str
    plan: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYMENT
# ─────────────────────────────────────────────────────────────────────────────

class EmploymentRecordOut(BaseModel):
    id: UUID4
    company_name: str
    job_title: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    location: Optional[str]
    company_domain: Optional[str]
    hr_email: Optional[str]
    verification_status: str
    verified_at: Optional[datetime]
    verified_by: Optional[str]
    confidence_score: Optional[int]
    notes: Optional[str]
    is_suspicious: bool
    fraud_reasons: list[Any]
    created_at: datetime

    class Config:
        from_attributes = True


class EmploymentRecordUpdate(BaseModel):
    hr_email: Optional[str] = None
    hr_phone: Optional[str] = None
    company_domain: Optional[str] = None
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# EDUCATION
# ─────────────────────────────────────────────────────────────────────────────

class EducationRecordOut(BaseModel):
    id: UUID4
    institution_name: str
    degree: Optional[str]
    field_of_study: Optional[str]
    graduation_year: Optional[int]
    institution_country: Optional[str]
    verification_status: str
    confidence_score: Optional[int]
    is_suspicious: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# FRAUD FLAGS
# ─────────────────────────────────────────────────────────────────────────────

class FraudFlagOut(BaseModel):
    id: UUID4
    flag_type: str
    severity: str
    description: str
    ai_reasoning: Optional[str]
    requires_review: bool
    reviewed_at: Optional[datetime]
    review_outcome: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FraudFlagReview(BaseModel):
    outcome: str = Field(..., pattern="^(confirmed|dismissed|escalated)$")
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# RISK SCORE
# ─────────────────────────────────────────────────────────────────────────────

class RiskScoreOut(BaseModel):
    id: UUID4
    overall_score: int
    risk_level: str
    employment_score: Optional[int]
    education_score: Optional[int]
    fraud_score: Optional[int]
    score_breakdown: dict
    confidence: float
    ai_reasoning: Optional[str]
    calculated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATE
# ─────────────────────────────────────────────────────────────────────────────

class CandidateOut(BaseModel):
    id: UUID4
    full_name: str
    status: str
    risk_score: Optional[int]
    risk_level: Optional[str]
    linkedin_url: Optional[str]
    employment_records: list[EmploymentRecordOut] = []
    education_records: list[EducationRecordOut] = []
    fraud_flags: list[FraudFlagOut] = []
    risk_scores: list[RiskScoreOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CandidateListItem(BaseModel):
    id: UUID4
    full_name: str
    status: str
    risk_score: Optional[int]
    risk_level: Optional[str]
    fraud_flag_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateListResponse(BaseModel):
    data: list[CandidateListItem]
    meta: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

class VerificationConfig(BaseModel):
    check_employment: bool = True
    check_education: bool = True
    check_public_records: bool = False
    allow_voice_calls: bool = False
    allow_emails: bool = True
    max_call_attempts: int = Field(default=2, ge=1, le=5)
    retry_days: int = Field(default=5, ge=1, le=14)


class VerificationCreate(BaseModel):
    candidate_id: UUID4
    config: VerificationConfig = Field(default_factory=VerificationConfig)


class VerificationOut(BaseModel):
    id: UUID4
    candidate_id: UUID4
    status: str
    config: dict
    celery_task_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# CONSENT
# ─────────────────────────────────────────────────────────────────────────────

class ConsentGrant(BaseModel):
    consent_type: str
    version: str = "1.0"


class ConsentOut(BaseModel):
    id: UUID4
    consent_type: str
    status: str
    granted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    expires_at: Optional[datetime]
    version: str
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL LOG
# ─────────────────────────────────────────────────────────────────────────────

class EmailLogOut(BaseModel):
    id: UUID4
    to_address: str
    subject: Optional[str]
    status: str
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    replied_at: Optional[datetime]
    ai_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: UUID4
    action: str
    entity_type: Optional[str]
    new_values: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION
# ─────────────────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: UUID4
    type: str
    title: Optional[str]
    message: Optional[str]
    data: dict
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC
# ─────────────────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
