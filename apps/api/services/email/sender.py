"""
TrustHire AI — Email service.
Default: Resend (3 000 free emails/month).
Fallback: plain SMTP (Gmail app password or self-hosted Postfix).
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings
from services.ai.model_router import ainvoke_llm

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SEND HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def _send_resend(to: str, subject: str, html: str) -> dict:
    import resend  # type: ignore

    resend.api_key = settings.resend_api_key
    resp = resend.Emails.send(
        {
            "from": settings.from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        }
    )
    return {"provider": "resend", "id": resp.get("id", "")}


def _send_smtp(to: str, subject: str, html: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user or settings.from_email
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as srv:
        srv.ehlo()
        srv.starttls()
        if settings.smtp_user and settings.smtp_pass:
            srv.login(settings.smtp_user, settings.smtp_pass)
        srv.send_message(msg)

    return {"provider": "smtp", "id": None}


async def send_email(to: str, subject: str, html: str) -> dict:
    """Route to configured provider."""
    if settings.email_provider == "resend" and settings.resend_api_key:
        return await _send_resend(to, subject, html)
    return _send_smtp(to, subject, html)


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYMENT VERIFICATION EMAIL
# ─────────────────────────────────────────────────────────────────────────────

async def send_employment_verification_email(
    to_email: str,
    company_name: str,
    candidate_name: str,
    job_title: str | None,
    start_date: str | None,
    end_date: str | None,
    verification_id: str,
) -> dict:
    """Generate and send an employment verification email."""

    prompt = f"""Write a professional, concise employment verification email to the HR department at {company_name}.

Purpose: Verify that {candidate_name} worked as {job_title or 'an employee'} 
from {start_date or 'an unspecified date'} to {end_date or 'present'}.

Include:
- A polite greeting
- Your purpose (employment background verification with candidate consent)
- The verification ID: {verification_id}
- A request to reply confirming or correcting the details
- A note that the candidate has consented to this check
- Professional sign-off from "TrustHire AI Verification Team"

Keep the email under 150 words. Do NOT add any details not listed above.
Return ONLY the email body text (no subject line). Use plain paragraph format.
"""

    body_text = await ainvoke_llm(prompt, task="email")
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6;">
<p>{body_html_escape(body_text)}</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0"/>
<p style="font-size:11px;color:#888;">
  Verification ID: {verification_id}<br/>
  This is an automated message from TrustHire AI on behalf of a verified recruiter.<br/>
  The candidate named above has provided written consent for this verification.
</p>
</body></html>
"""

    subject = f"Employment Verification Request — {candidate_name} (ID: {verification_id[:8]})"
    result = await send_email(to_email, subject, body_html)
    logger.info("Sent employment verification email to %s — %s", to_email, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# EDUCATION VERIFICATION EMAIL
# ─────────────────────────────────────────────────────────────────────────────

async def send_education_verification_email(
    to_email: str,
    institution_name: str,
    candidate_name: str,
    degree: str | None,
    graduation_year: int | None,
    verification_id: str,
) -> dict:
    subject = f"Education Verification Request — {candidate_name}"
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6;">
<p>Dear Registrar / Records Office,</p>
<p>We are conducting an education background verification for <strong>{candidate_name}</strong>, 
who listed {institution_name} on their application. They claim to have received a 
{degree or 'qualification'} in {graduation_year or 'an unspecified year'}.</p>
<p>We kindly request confirmation of these details, or correction if they are inaccurate. 
The candidate has given written consent for this verification.</p>
<p>Verification ID: <strong>{verification_id}</strong></p>
<p>Please reply to this email with confirmation.<br/>
Thank you for your time.</p>
<p>TrustHire AI Verification Team</p>
</body></html>
"""
    result = await send_email(to_email, subject, body_html)
    logger.info("Sent education verification email to %s", to_email)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION EMAIL
# ─────────────────────────────────────────────────────────────────────────────

async def send_notification_email(
    to_email: str,
    subject: str,
    body_text: str,
) -> dict:
    html = f"""
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6;">
<p>{body_html_escape(body_text)}</p>
<hr style="border:none;border-top:1px solid #eee;margin:16px 0"/>
<p style="font-size:11px;color:#888;">TrustHire AI · {datetime.utcnow().strftime('%Y-%m-%d')}</p>
</body></html>
"""
    return await send_email(to_email, subject, html)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def body_html_escape(text: str) -> str:
    """Minimal HTML escaping and newline → <br/> conversion."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("\n", "<br/>")
