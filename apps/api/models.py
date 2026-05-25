"""
TrustHire AI — All database models.
Import from this single module to avoid circular imports.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, SmallInteger, Boolean,
    ForeignKey, Float, Date, DateTime, 
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship
from .database import Base


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZATION
# ─────────────────────────────────────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(255), nullable=False)
    slug       = Column(String(100), unique=True, nullable=False)
    plan       = Column(String(50), default="starter")
    settings   = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    users      = relationship("User", back_populates="organization")
    candidates = relationship("Candidate", back_populates="organization")


# ─────────────────────────────────────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    google_id       = Column(String(255), unique=True, nullable=True)
    email           = Column(String(255), nullable=False, unique=True)
    full_name       = Column(String(255), nullable=True)
    avatar_url      = Column(Text, nullable=True)
    role            = Column(String(50), nullable=False, default="recruiter")
    is_active       = Column(Boolean, default=True)
    last_login      = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at      = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at      = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="users")


# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATE
# ─────────────────────────────────────────────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    full_name       = Column(String(255), nullable=False)
    email           = Column(Text, nullable=True)       # AES-encrypted at app layer
    phone           = Column(String(100), nullable=True) # AES-encrypted at app layer
    raw_text        = Column(Text, nullable=True)
    parsed_data     = Column(JSONB, nullable=True)
    linkedin_url    = Column(Text, nullable=True)
    status          = Column(String(50), default="pending", nullable=False)
    risk_score      = Column(SmallInteger, nullable=True)
    risk_level      = Column(String(20), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at      = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at      = Column(DateTime(timezone=True), nullable=True)

    organization       = relationship("Organization", back_populates="candidates")
    documents          = relationship("Document", back_populates="candidate", lazy="selectin")
    employment_records = relationship("EmploymentRecord", back_populates="candidate", lazy="selectin")
    education_records  = relationship("EducationRecord", back_populates="candidate", lazy="selectin")
    fraud_flags        = relationship("FraudFlag", back_populates="candidate", lazy="selectin")
    consent_records    = relationship("ConsentRecord", back_populates="candidate")
    risk_scores        = relationship("RiskScore", back_populates="candidate", lazy="selectin")
    verification_requests = relationship("VerificationRequest", back_populates="candidate")


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT
# ─────────────────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    file_name    = Column(String(500), nullable=False)
    file_size    = Column(Integer, nullable=True)
    mime_type    = Column(String(100), nullable=True)
    storage_path = Column(Text, nullable=False)
    checksum     = Column(String(64), nullable=True)
    doc_type     = Column(String(50), default="resume")
    ocr_text     = Column(Text, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    scan_status  = Column(String(30), default="pending")
    scanned_at   = Column(DateTime(timezone=True), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="documents")


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICATION REQUEST
# ─────────────────────────────────────────────────────────────────────────────

class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    candidate_id    = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    requested_by    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status          = Column(String(50), default="pending", nullable=False)
    config          = Column(JSONB, default=dict)
    celery_task_id  = Column(String(255), nullable=True)
    started_at      = Column(DateTime(timezone=True), nullable=True)
    completed_at    = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at      = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="verification_requests")


# ─────────────────────────────────────────────────────────────────────────────
# CONSENT RECORD
# ─────────────────────────────────────────────────────────────────────────────

class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column(String(100), nullable=False)
    status       = Column(String(30), nullable=False, default="pending")
    granted_at   = Column(DateTime(timezone=True), nullable=True)
    revoked_at   = Column(DateTime(timezone=True), nullable=True)
    expires_at   = Column(DateTime(timezone=True), nullable=True)
    ip_address   = Column(INET, nullable=True)
    user_agent   = Column(Text, nullable=True)
    consent_text = Column(Text, nullable=False)
    version      = Column(String(20), default="1.0")
    created_at   = Column(DateTime(timezone=True), default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="consent_records")


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYMENT RECORD
# ─────────────────────────────────────────────────────────────────────────────

class EmploymentRecord(Base):
    __tablename__ = "employment_records"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id        = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    company_name        = Column(String(500), nullable=False)
    job_title           = Column(String(500), nullable=True)
    start_date          = Column(String(20), nullable=True)
    end_date            = Column(String(20), nullable=True)
    location            = Column(String(500), nullable=True)
    responsibilities    = Column(Text, nullable=True)
    company_domain      = Column(String(255), nullable=True)
    hr_email            = Column(String(255), nullable=True)
    hr_phone            = Column(String(100), nullable=True)
    verification_status = Column(String(50), default="pending")
    verified_at         = Column(DateTime(timezone=True), nullable=True)
    verified_by         = Column(String(50), nullable=True)
    verifier_name       = Column(String(255), nullable=True)
    confidence_score    = Column(Integer, nullable=True)
    notes               = Column(Text, nullable=True)
    is_suspicious       = Column(Boolean, default=False)
    fraud_reasons       = Column(JSONB, default=list)
    created_at          = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at          = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate   = relationship("Candidate", back_populates="employment_records")
    email_logs  = relationship("EmailLog", back_populates="employment_record")


# ─────────────────────────────────────────────────────────────────────────────
# EDUCATION RECORD
# ─────────────────────────────────────────────────────────────────────────────

class EducationRecord(Base):
    __tablename__ = "education_records"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id         = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    institution_name     = Column(String(500), nullable=False)
    degree               = Column(String(255), nullable=True)
    field_of_study       = Column(String(255), nullable=True)
    graduation_year      = Column(SmallInteger, nullable=True)
    gpa                  = Column(Float, nullable=True)
    institution_country  = Column(String(100), nullable=True)
    accreditation_body   = Column(String(255), nullable=True)
    verification_status  = Column(String(50), default="pending")
    verified_at          = Column(DateTime(timezone=True), nullable=True)
    verified_by          = Column(String(50), nullable=True)
    confidence_score     = Column(Integer, nullable=True)
    notes                = Column(Text, nullable=True)
    is_suspicious        = Column(Boolean, default=False)
    fraud_reasons        = Column(JSONB, default=list)
    created_at           = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at           = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="education_records")


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL LOG
# ─────────────────────────────────────────────────────────────────────────────

class EmailLog(Base):
    __tablename__ = "email_logs"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_request_id = Column(UUID(as_uuid=True), ForeignKey("verification_requests.id"), nullable=True)
    employment_record_id    = Column(UUID(as_uuid=True), ForeignKey("employment_records.id"), nullable=True)
    to_address              = Column(String(255), nullable=False)
    from_address            = Column(String(255), nullable=False)
    subject                 = Column(Text, nullable=True)
    body_html               = Column(Text, nullable=True)
    status                  = Column(String(30), default="pending")
    provider_message_id     = Column(String(255), nullable=True)
    opened_at               = Column(DateTime(timezone=True), nullable=True)
    replied_at              = Column(DateTime(timezone=True), nullable=True)
    reply_text              = Column(Text, nullable=True)
    reply_verified          = Column(Boolean, nullable=True)
    ai_summary              = Column(Text, nullable=True)
    followup_count          = Column(Integer, default=0)
    sent_at                 = Column(DateTime(timezone=True), nullable=True)
    created_at              = Column(DateTime(timezone=True), default=datetime.utcnow)

    employment_record = relationship("EmploymentRecord", back_populates="email_logs")


# ─────────────────────────────────────────────────────────────────────────────
# FRAUD FLAG
# ─────────────────────────────────────────────────────────────────────────────

class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id    = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    flag_type       = Column(String(100), nullable=False)
    severity        = Column(String(20), nullable=False)
    description     = Column(Text, nullable=False)
    evidence        = Column(JSONB, default=dict)
    ai_reasoning    = Column(Text, nullable=True)
    requires_review = Column(Boolean, default=True)
    reviewed_by     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at     = Column(DateTime(timezone=True), nullable=True)
    review_outcome  = Column(String(50), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="fraud_flags")


# ─────────────────────────────────────────────────────────────────────────────
# RISK SCORE
# ─────────────────────────────────────────────────────────────────────────────

class RiskScore(Base):
    __tablename__ = "risk_scores"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id            = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    verification_request_id = Column(UUID(as_uuid=True), ForeignKey("verification_requests.id"), nullable=True)
    overall_score           = Column(SmallInteger, nullable=False)
    risk_level              = Column(String(20), nullable=False)
    employment_score        = Column(SmallInteger, nullable=True)
    education_score         = Column(SmallInteger, nullable=True)
    fraud_score             = Column(SmallInteger, nullable=True)
    public_record_score     = Column(SmallInteger, nullable=True)
    score_breakdown         = Column(JSONB, nullable=False, default=dict)
    confidence              = Column(Float, nullable=False, default=0.8)
    ai_reasoning            = Column(Text, nullable=True)
    calculated_at           = Column(DateTime(timezone=True), default=datetime.utcnow)
    model_version           = Column(String(50), default="1.0")

    candidate = relationship("Candidate", back_populates="risk_scores")


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG  (append-only — never soft-delete)
# ─────────────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)
    user_id         = Column(UUID(as_uuid=True), nullable=True)
    candidate_id    = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=True)
    action          = Column(String(200), nullable=False)
    entity_type     = Column(String(100), nullable=True)
    entity_id       = Column(UUID(as_uuid=True), nullable=True)
    old_values      = Column(JSONB, nullable=True)
    new_values      = Column(JSONB, nullable=True)
    ip_address      = Column(INET, nullable=True)
    user_agent      = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION
# ─────────────────────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    type            = Column(String(100), nullable=False)
    title           = Column(String(500), nullable=True)
    message         = Column(Text, nullable=True)
    data            = Column(JSONB, default=dict)
    is_read         = Column(Boolean, default=False)
    read_at         = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
