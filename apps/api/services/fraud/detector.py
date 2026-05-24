"""
TrustHire AI — Fraud detection service.
Analyses parsed resume data for suspicious patterns.
All findings are flags for HUMAN review — never automatic determinations.
"""

import logging
import re
from datetime import date, datetime
from typing import Any

from services.ai.model_router import ainvoke_llm

logger = logging.getLogger(__name__)

# Severity weights for risk score contribution
FLAG_WEIGHTS: dict[str, dict] = {
    "overlapping_employment":     {"score": 30, "severity": "high"},
    "impossible_experience":      {"score": 35, "severity": "high"},
    "ai_generated_resume":        {"score": 20, "severity": "medium"},
    "suspicious_institution":     {"score": 15, "severity": "medium"},
    "future_graduation_date":     {"score": 40, "severity": "high"},
    "impossible_graduation_date": {"score": 40, "severity": "high"},
    "suspicious_email_domain":    {"score": 10, "severity": "low"},
    "timeline_gap_excessive":     {"score": 10, "severity": "low"},
    "duplicate_company_entry":    {"score": 15, "severity": "medium"},
}

_FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "protonmail.com", "yandex.com", "mail.com", "icloud.com",
    "zoho.com", "aol.com",
}


# ─────────────────────────────────────────────────────────────────────────────
# DATE PARSING
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(date_str: str | None) -> date | None:
    if not date_str or date_str.lower() == "present":
        return date.today()
    for fmt in ("%Y-%m", "%Y"):
        try:
            return datetime.strptime(date_str[:len(fmt)], fmt).date()
        except ValueError:
            continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def check_overlapping_employment(employment: list[dict]) -> list[dict]:
    """Detect jobs whose date ranges overlap by more than 30 days."""
    flags = []
    dated = []
    for job in employment:
        start = _parse_date(job.get("start_date"))
        end   = _parse_date(job.get("end_date"))
        if start and end:
            dated.append((start, end, job.get("company_name", "Unknown")))

    for i, (s1, e1, c1) in enumerate(dated):
        for s2, e2, c2 in dated[i + 1:]:
            overlap_start = max(s1, s2)
            overlap_end   = min(e1, e2)
            overlap_days  = (overlap_end - overlap_start).days
            if overlap_days > 30:
                flags.append({
                    "flag_type": "overlapping_employment",
                    "severity": FLAG_WEIGHTS["overlapping_employment"]["severity"],
                    "description": (
                        f"Dates overlap by {overlap_days} days: "
                        f"'{c1}' and '{c2}'"
                    ),
                    "evidence": {
                        "company_a": c1, "company_b": c2,
                        "overlap_days": overlap_days,
                    },
                })
    return flags


def check_impossible_experience(employment: list[dict]) -> list[dict]:
    """Total claimed experience cannot exceed years since first job start."""
    flags = []
    starts = [_parse_date(j.get("start_date")) for j in employment]
    starts = [s for s in starts if s]
    if not starts:
        return flags

    earliest = min(starts)
    career_years = (date.today() - earliest).days / 365.25

    total_claimed = 0.0
    for job in employment:
        s = _parse_date(job.get("start_date"))
        e = _parse_date(job.get("end_date"))
        if s and e:
            total_claimed += max(0, (e - s).days) / 365.25

    if total_claimed > career_years + 2:
        flags.append({
            "flag_type": "impossible_experience",
            "severity": FLAG_WEIGHTS["impossible_experience"]["severity"],
            "description": (
                f"Claims {total_claimed:.1f} years of experience but career "
                f"spans only {career_years:.1f} years since first listed job."
            ),
            "evidence": {
                "claimed_years": round(total_claimed, 1),
                "career_span_years": round(career_years, 1),
            },
        })
    return flags


def check_suspicious_hr_domains(employment: list[dict]) -> list[dict]:
    """Flag HR contact emails that use free email providers."""
    flags = []
    for job in employment:
        hr_email = job.get("hr_email", "")
        if not hr_email:
            continue
        domain = hr_email.split("@")[-1].lower() if "@" in hr_email else ""
        if domain in _FREE_EMAIL_DOMAINS:
            flags.append({
                "flag_type": "suspicious_email_domain",
                "severity": FLAG_WEIGHTS["suspicious_email_domain"]["severity"],
                "description": (
                    f"HR contact email '{hr_email}' at '{job.get('company_name')}' "
                    f"uses a free email domain — legitimate companies use corporate email."
                ),
                "evidence": {"hr_email": hr_email, "domain": domain},
            })
    return flags


def check_duplicate_companies(employment: list[dict]) -> list[dict]:
    """Detect the same company listed more than once with no explanation."""
    flags = []
    names = [j.get("company_name", "").lower().strip() for j in employment]
    seen: set[str] = set()
    for name in names:
        if name in seen:
            flags.append({
                "flag_type": "duplicate_company_entry",
                "severity": FLAG_WEIGHTS["duplicate_company_entry"]["severity"],
                "description": f"Company '{name}' appears more than once in employment history.",
                "evidence": {"company": name},
            })
        seen.add(name)
    return flags


def check_education_dates(education: list[dict]) -> list[dict]:
    """Flag graduation years that are in the future or implausibly old."""
    flags = []
    current_year = date.today().year
    for edu in education:
        year = edu.get("graduation_year")
        if year is None:
            continue
        if year > current_year:
            flags.append({
                "flag_type": "future_graduation_date",
                "severity": FLAG_WEIGHTS["future_graduation_date"]["severity"],
                "description": f"Graduation year {year} is in the future.",
                "evidence": {"institution": edu.get("institution_name"), "year": year},
            })
        elif year < 1900:
            flags.append({
                "flag_type": "impossible_graduation_date",
                "severity": FLAG_WEIGHTS["impossible_graduation_date"]["severity"],
                "description": f"Graduation year {year} is implausible.",
                "evidence": {"institution": edu.get("institution_name"), "year": year},
            })
    return flags


async def check_ai_generated(raw_text: str) -> list[dict]:
    """Ask the LLM to score likelihood of AI-generated content."""
    if not raw_text or len(raw_text) < 200:
        return []

    prompt = f"""Score this resume text on a scale of 0.0 to 1.0 for likelihood of being AI-generated.
Consider: unnaturally perfect grammar, generic buzzword-heavy phrasing, lack of specific personal
details, uniform sentence structure, overly polished language throughout.

Return ONLY a single float between 0.0 and 1.0. Nothing else.

Text (first 2000 chars):
{raw_text[:2000]}
"""
    try:
        result = await ainvoke_llm(prompt, task="fraud")
        score = float(result.strip().split()[0])
        score = max(0.0, min(1.0, score))
    except (ValueError, IndexError):
        return []

    if score >= 0.80:
        return [{
            "flag_type": "ai_generated_resume",
            "severity": FLAG_WEIGHTS["ai_generated_resume"]["severity"],
            "description": f"Resume shows {score:.0%} probability of AI generation.",
            "evidence": {"ai_score": round(score, 3)},
        }]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def run_fraud_analysis(
    parsed_data: dict,
    raw_text: str = "",
) -> list[dict]:
    """
    Run all fraud checks and return a flat list of flag dicts.
    Each flag: {flag_type, severity, description, evidence}.
    """
    employment = parsed_data.get("employment_history", []) or []
    education  = parsed_data.get("education_history", []) or []

    flags: list[dict] = []
    flags.extend(check_overlapping_employment(employment))
    flags.extend(check_impossible_experience(employment))
    flags.extend(check_suspicious_hr_domains(employment))
    flags.extend(check_duplicate_companies(employment))
    flags.extend(check_education_dates(education))

    ai_flags = await check_ai_generated(raw_text)
    flags.extend(ai_flags)

    logger.info("Fraud analysis complete — %d flags found", len(flags))
    return flags
