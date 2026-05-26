"""
TrustHire AI — Consent management (GDPR / DPDP Act 2023).
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update

from ...database import AsyncSessionLocal
from ...middleware.audit import audit_log
from ...models import ConsentRecord

logger = logging.getLogger(__name__)


class ConsentMissingError(Exception):
    pass


class ConsentExpiredError(Exception):
    pass


CONSENT_DEFINITIONS: dict[str, dict] = {
    "data_processing": {
        "title": "Personal Data Processing",
        "description": (
            "Processing of your personal information for background verification "
            "under GDPR Article 6(1)(a) / DPDP Act 2023 Section 4."
        ),
        "retention_days": 365,
        "required": True,
    },
    "employment_verification": {
        "title": "Employment History Verification",
        "description": "Contacting previous employers to verify your employment history via email.",
        "retention_days": 365,
        "required": False,
    },
    "education_verification": {
        "title": "Education Records Verification",
        "description": "Contacting educational institutions to verify your qualifications.",
        "retention_days": 365,
        "required": False,
    },
    "voice_call_consent": {
        "title": "AI Voice Call Authorization",
        "description": (
            "Authorizing AI-powered automated phone calls to HR departments of your "
            "listed employers. Calls are recorded for compliance. AI-generated voice "
            "(text-to-speech) technology is used."
        ),
        "retention_days": 365,
        "required": False,
    },
    "email_contact": {
        "title": "Email Contact Authorization",
        "description": "Sending verification emails to HR of your listed employers.",
        "retention_days": 365,
        "required": False,
    },
    "criminal_check": {
        "title": "Public Records Search",
        "description": (
            "Searching legally accessible public databases (sanctions lists, public "
            "corporate records). This does NOT access police or law-enforcement databases."
        ),
        "retention_days": 365,
        "required": False,
    },
}


async def get_active_consent(candidate_id: str, consent_type: str) -> ConsentRecord | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ConsentRecord).where(
                ConsentRecord.candidate_id == uuid.UUID(candidate_id),
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.status == "granted",
                ConsentRecord.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


async def grant_consent(
    candidate_id: str,
    consent_type: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    version: str = "1.0",
) -> ConsentRecord:
    """Record explicit, granular consent. Idempotent — ignores duplicates."""

    if consent_type not in CONSENT_DEFINITIONS:
        raise ValueError(f"Unknown consent type: {consent_type!r}")

    defn = CONSENT_DEFINITIONS[consent_type]
    expires_at = datetime.utcnow() + timedelta(days=defn["retention_days"])

    consent_text = (
        f"CONSENT RECORD v{version}\n"
        f"Purpose: {defn['title']}\n"
        f"Description: {defn['description']}\n"
        f"Retention period: {defn['retention_days']} days\n"
        f"Granted at: {datetime.utcnow().isoformat()}Z\n"
        f"IP: {ip_address or 'unknown'}\n"
        f"You may withdraw this consent at any time."
    )

    async with AsyncSessionLocal() as db:
        existing = await get_active_consent(candidate_id, consent_type)
        if existing:
            return existing

        record = ConsentRecord(
            candidate_id=uuid.UUID(candidate_id),
            consent_type=consent_type,
            status="granted",
            granted_at=datetime.utcnow(),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text=consent_text,
            version=version,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

    await audit_log(
        action="consent.granted",
        candidate_id=candidate_id,
        new_values={"consent_type": consent_type, "version": version},
        ip_address=ip_address,
    )

    return record


async def revoke_consent(
    candidate_id: str,
    consent_type: str,
    reason: str | None = None,
) -> None:
    """Revoke a previously granted consent. Triggers downstream halts."""

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ConsentRecord)
            .where(
                ConsentRecord.candidate_id == uuid.UUID(candidate_id),
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.status == "granted",
            )
            .values(status="revoked", revoked_at=datetime.utcnow())
        )
        await db.commit()

    if consent_type == "data_processing":
        await _halt_all_processing(candidate_id)

    await audit_log(
        action="consent.revoked",
        candidate_id=candidate_id,
        new_values={"consent_type": consent_type, "reason": reason},
    )


async def _halt_all_processing(candidate_id: str) -> None:
    """Cancel all active verification tasks for a candidate."""
    from sqlalchemy import select as sa_select
    from models import VerificationRequest

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_select(VerificationRequest).where(
                VerificationRequest.candidate_id == uuid.UUID(candidate_id),
                VerificationRequest.status.in_(["pending", "running"]),
            )
        )
        for verif in result.scalars().all():
            if verif.celery_task_id:
                try:
                    from tasks.celery_app import celery_app
                    celery_app.control.revoke(verif.celery_task_id, terminate=True)
                except Exception as exc:
                    logger.warning("Could not revoke Celery task %s: %s", verif.celery_task_id, exc)
            verif.status = "cancelled"
        await db.commit()

    logger.info("Halted all processing for candidate %s after consent revocation", candidate_id)


async def verify_consents_for_verification(
    candidate_id: str,
    config: dict,
) -> None:
    """
    Check all required consents before starting a verification workflow.
    Raises ConsentMissingError if any are absent.
    """
    required = ["data_processing"]

    if config.get("check_employment") or config.get("allow_emails"):
        required.append("employment_verification")
        required.append("email_contact")

    if config.get("allow_voice_calls"):
        required.append("voice_call_consent")

    if config.get("check_education"):
        required.append("education_verification")

    if config.get("check_public_records"):
        required.append("criminal_check")

    for ctype in required:
        record = await get_active_consent(candidate_id, ctype)
        if not record:
            defn = CONSENT_DEFINITIONS.get(ctype, {})
            raise ConsentMissingError(
                f"Missing consent for: '{defn.get('title', ctype)}'. "
                "Obtain explicit candidate consent before proceeding."
            )
        if record.expires_at and record.expires_at < datetime.utcnow():
            raise ConsentExpiredError(
                f"Consent expired for: '{ctype}'. Please renew candidate consent."
            )
