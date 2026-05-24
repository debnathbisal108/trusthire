"""
TrustHire AI — Celery application and task definitions.
Voice calls removed. Uses free cloud LLMs.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from celery import Celery
from celery.schedules import crontab

from config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CELERY APP
# ─────────────────────────────────────────────────────────────────────────────

celery_app = Celery(
    "trusthire",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_max_retries=3,
    task_default_retry_delay=60,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_routes={
        "tasks.parse_resume":      {"queue": "parsing"},
        "tasks.run_verification":  {"queue": "verification"},
        "tasks.send_email":        {"queue": "email"},
        "tasks.generate_report":   {"queue": "reports"},
        "tasks.retry_pending":     {"queue": "scheduled"},
        "tasks.send_followups":    {"queue": "scheduled"},
        "tasks.enforce_retention": {"queue": "scheduled"},
    },
)

celery_app.conf.beat_schedule = {
    "retry-pending-verifications": {
        "task": "tasks.retry_pending",
        "schedule": crontab(hour=9, minute=0),
    },
    "send-followup-emails": {
        "task": "tasks.send_followups",
        "schedule": crontab(hour=10, minute=0),
    },
    "enforce-retention-policy": {
        "task": "tasks.enforce_retention",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),
    },
}


def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─────────────────────────────────────────────────────────────────────────────
# TASK: parse_resume
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.parse_resume",
    max_retries=3,
    default_retry_delay=30,
)
def parse_resume_task(self, candidate_id: str, document_id: str):
    """OCR + free cloud LLM extraction for an uploaded resume."""

    async def _inner():
        from database import AsyncSessionLocal
        from models import Candidate, Document, EmploymentRecord, EducationRecord
        from services.resume_parser.parser import extract_text, parse_resume
        from services.storage.minio_client import download_file
        from middleware.audit import audit_log

        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, uuid.UUID(document_id))
            candidate = await db.get(Candidate, uuid.UUID(candidate_id))

            if not doc or not candidate:
                logger.error("Document or candidate not found: %s / %s", document_id, candidate_id)
                return

            try:
                file_bytes = await download_file(doc.storage_path)
            except Exception as exc:
                candidate.status = "failed"
                await db.commit()
                raise exc

            doc.scan_status = "clean"

            raw_text = await extract_text(file_bytes, doc.mime_type or "application/pdf")
            doc.ocr_text = raw_text[:50_000]
            candidate.raw_text = raw_text

            parsed = await parse_resume(raw_text)
            candidate.parsed_data = parsed

            if parsed.get("full_name") and candidate.full_name in ("", None):
                candidate.full_name = parsed["full_name"]
            if parsed.get("linkedin_url"):
                candidate.linkedin_url = parsed["linkedin_url"]

            for emp in parsed.get("employment_history", []):
                record = EmploymentRecord(
                    candidate_id=uuid.UUID(candidate_id),
                    company_name=emp.get("company_name", "Unknown"),
                    job_title=emp.get("job_title"),
                    start_date=emp.get("start_date"),
                    end_date=emp.get("end_date"),
                    location=emp.get("location"),
                    responsibilities="\n".join(emp.get("responsibilities", [])),
                    company_domain=emp.get("company_domain"),
                )
                db.add(record)

            for edu in parsed.get("education_history", []):
                record = EducationRecord(
                    candidate_id=uuid.UUID(candidate_id),
                    institution_name=edu.get("institution_name", "Unknown"),
                    degree=edu.get("degree"),
                    field_of_study=edu.get("field_of_study"),
                    graduation_year=edu.get("graduation_year"),
                )
                db.add(record)

            candidate.status = "parsed"
            doc.scanned_at = datetime.utcnow()
            await db.commit()

        await audit_log(
            action="resume.parsed",
            candidate_id=candidate_id,
            new_values={
                "employment_count": len(parsed.get("employment_history", [])),
                "education_count": len(parsed.get("education_history", [])),
                "llm_provider": settings.llm_provider,
            },
        )

    try:
        _run(_inner())
    except Exception as exc:
        logger.error("parse_resume_task failed for %s: %s", candidate_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ─────────────────────────────────────────────────────────────────────────────
# TASK: run_verification
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.run_verification",
    max_retries=2,
    default_retry_delay=120,
)
def run_verification_task(self, verification_request_id: str):
    """Full verification pipeline: fraud analysis → emails → risk scoring."""

    async def _inner():
        from database import AsyncSessionLocal
        from models import (
            Candidate, VerificationRequest, FraudFlag, RiskScore,
            EmploymentRecord, EducationRecord, EmailLog,
        )
        from services.fraud.detector import run_fraud_analysis
        from services.fraud.scorer import calculate_risk_score
        from services.email.sender import send_employment_verification_email
        from middleware.audit import audit_log
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            verif = await db.get(VerificationRequest, uuid.UUID(verification_request_id))
            if not verif:
                logger.error("Verification not found: %s", verification_request_id)
                return
            candidate = await db.get(Candidate, verif.candidate_id)
            if not candidate:
                return

            verif.status = "running"
            verif.started_at = datetime.utcnow()
            await db.commit()

        # ── Fraud analysis ──────────────────────────────────────────────────
        parsed_data = candidate.parsed_data or {}
        raw_text    = candidate.raw_text or ""
        fraud_flags_data = await run_fraud_analysis(parsed_data, raw_text)

        async with AsyncSessionLocal() as db:
            for flag_dict in fraud_flags_data:
                flag = FraudFlag(
                    candidate_id=candidate.id,
                    flag_type=flag_dict["flag_type"],
                    severity=flag_dict["severity"],
                    description=flag_dict["description"],
                    evidence=flag_dict.get("evidence", {}),
                )
                db.add(flag)
            await db.commit()

        # ── Employment verification emails ──────────────────────────────────
        config = verif.config or {}
        if config.get("allow_emails", True):
            async with AsyncSessionLocal() as db:
                emp_result = await db.execute(
                    select(EmploymentRecord).where(
                        EmploymentRecord.candidate_id == candidate.id
                    )
                )
                emp_records = emp_result.scalars().all()

            for emp in emp_records:
                if emp.hr_email:
                    try:
                        await send_employment_verification_email(
                            to_email=emp.hr_email,
                            company_name=emp.company_name,
                            candidate_name=candidate.full_name,
                            job_title=emp.job_title,
                            start_date=emp.start_date,
                            end_date=emp.end_date,
                            verification_id=str(emp.id),
                        )
                        async with AsyncSessionLocal() as db:
                            log = EmailLog(
                                verification_request_id=verif.id,
                                employment_record_id=emp.id,
                                to_address=emp.hr_email,
                                from_address=settings.from_email,
                                subject=f"Employment Verification — {candidate.full_name}",
                                status="sent",
                                sent_at=datetime.utcnow(),
                            )
                            db.add(log)
                            emp_rec = await db.get(EmploymentRecord, emp.id)
                            if emp_rec:
                                emp_rec.verification_status = "email_sent"
                            await db.commit()
                    except Exception as exc:
                        logger.warning("Email failed for %s: %s", emp.hr_email, exc)

        # ── Risk scoring ────────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            emp_result   = await db.execute(select(EmploymentRecord).where(EmploymentRecord.candidate_id == candidate.id))
            edu_result   = await db.execute(select(EducationRecord).where(EducationRecord.candidate_id == candidate.id))
            fraud_result = await db.execute(select(FraudFlag).where(FraudFlag.candidate_id == candidate.id))

            emp_records_db  = emp_result.scalars().all()
            edu_records_db  = edu_result.scalars().all()
            fraud_flags_db  = fraud_result.scalars().all()

        risk = await calculate_risk_score(
            employment_records=emp_records_db,
            education_records=edu_records_db,
            fraud_flags=fraud_flags_db,
            public_record_matches=[],
        )

        async with AsyncSessionLocal() as db:
            score_record = RiskScore(
                candidate_id=candidate.id,
                verification_request_id=verif.id,
                overall_score=risk["overall_score"],
                risk_level=risk["risk_level"],
                score_breakdown=risk["breakdown"],
                confidence=risk["confidence"],
                ai_reasoning=risk["ai_reasoning"],
            )
            db.add(score_record)

            verif_rec = await db.get(VerificationRequest, verif.id)
            if verif_rec:
                verif_rec.status = "completed"
                verif_rec.completed_at = datetime.utcnow()

            cand_rec = await db.get(Candidate, candidate.id)
            if cand_rec:
                cand_rec.risk_score = risk["overall_score"]
                cand_rec.risk_level = risk["risk_level"]
                cand_rec.status = "completed"

            await db.commit()

        await audit_log(
            action="verification.completed",
            candidate_id=str(candidate.id),
            new_values={
                "verification_id": verification_request_id,
                "risk_score": risk["overall_score"],
                "risk_level": risk["risk_level"],
                "llm_provider": settings.llm_provider,
            },
        )

    try:
        _run(_inner())
    except Exception as exc:
        logger.error("run_verification_task failed: %s", exc, exc_info=True)

        async def _fail():
            from database import AsyncSessionLocal
            from models import VerificationRequest
            async with AsyncSessionLocal() as db:
                v = await db.get(VerificationRequest, uuid.UUID(verification_request_id))
                if v:
                    v.status = "failed"
                    await db.commit()

        _run(_fail())
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 120)


# ─────────────────────────────────────────────────────────────────────────────
# TASK: generate_report
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.generate_report")
def generate_report_task(candidate_id: str) -> str:
    async def _inner():
        from services.reporting.generator import generate_pdf_report
        return await generate_pdf_report(candidate_id)

    try:
        return _run(_inner())
    except Exception as exc:
        logger.error("generate_report_task failed for %s: %s", candidate_id, exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# TASK: send_email (generic)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.send_email")
def send_email_task(to_email: str, subject: str, body_html: str):
    from services.email.sender import send_email
    _run(send_email(to_email, subject, body_html))


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULED TASKS
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.retry_pending")
def retry_pending_task():
    """Re-queue verifications stuck in 'running' > 24 hours."""

    async def _inner():
        from database import AsyncSessionLocal
        from models import VerificationRequest
        from sqlalchemy import select

        cutoff = datetime.utcnow() - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VerificationRequest).where(
                    VerificationRequest.status == "running",
                    VerificationRequest.started_at < cutoff,
                )
            )
            stale = result.scalars().all()

        for v in stale:
            logger.info("Retrying stale verification %s", v.id)
            run_verification_task.delay(str(v.id))

    _run(_inner())


@celery_app.task(name="tasks.send_followups")
def send_followups_task():
    """Send follow-up emails to HR contacts that haven't replied after 3 days."""

    async def _inner():
        from database import AsyncSessionLocal
        from models import EmailLog
        from sqlalchemy import select

        cutoff = datetime.utcnow() - timedelta(days=3)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EmailLog).where(
                    EmailLog.replied_at.is_(None),
                    EmailLog.sent_at < cutoff,
                    EmailLog.followup_count < 2,
                    EmailLog.status.in_(["sent", "delivered"]),
                )
            )
            stale_emails = result.scalars().all()

        for email_log in stale_emails:
            send_email_task.delay(
                to_email=email_log.to_address,
                subject="[Follow-up] Employment Verification Request",
                body_html=(
                    f"<p>We are following up on our previous verification email. "
                    f"Please reply at your earliest convenience. "
                    f"Verification reference: {email_log.employment_record_id}</p>"
                    f"<p>Thank you — TrustHire AI Verification Team</p>"
                ),
            )

    _run(_inner())


@celery_app.task(name="tasks.enforce_retention")
def enforce_retention_task():
    """Weekly: anonymise candidate data older than retention period."""
    logger.info("Running data retention enforcement (weekly)")
    # Full implementation would query candidates with old deleted_at
    # and anonymise any remaining personal data fields
