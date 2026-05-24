"""
TrustHire AI — Risk scoring engine.
Produces a 0–100 score with explainable breakdown.
Higher score = higher risk.
"""

import logging
from services.ai.model_router import ainvoke_llm

logger = logging.getLogger(__name__)

_FLAG_SEVERITY_WEIGHTS = {
    "critical": 50,
    "high":     30,
    "medium":   15,
    "low":      8,
}

_COMPONENT_WEIGHTS = {
    "employment":    0.35,
    "education":     0.25,
    "fraud":         0.25,
    "public_records": 0.10,
    "digital":       0.05,
}


def _clamp(val: float) -> int:
    return max(0, min(100, round(val)))


async def calculate_risk_score(
    employment_records: list,
    education_records: list,
    fraud_flags: list,
    public_record_matches: list,
) -> dict:
    """
    Calculate overall risk score with per-component breakdown.

    Returns:
        {
          overall_score: int,
          risk_level: str,
          breakdown: { component: {score, weight, reasoning} },
          ai_reasoning: str,
          confidence: float,
        }
    """

    breakdown: dict = {}

    # ── Employment (35 %) ───────────────────────────────────────────────────
    emp_total    = len(employment_records)
    emp_verified = sum(1 for e in employment_records if e.verification_status == "verified")
    emp_ratio    = (emp_verified / emp_total) if emp_total > 0 else 0.5
    emp_score    = _clamp((1 - emp_ratio) * 100)

    breakdown["employment"] = {
        "score": emp_score,
        "weight": _COMPONENT_WEIGHTS["employment"],
        "verified": emp_verified,
        "total": emp_total,
        "reasoning": f"{emp_verified}/{emp_total} employment records verified.",
    }

    # ── Education (25 %) ────────────────────────────────────────────────────
    edu_total    = len(education_records)
    edu_verified = sum(1 for e in education_records if e.verification_status == "verified")
    edu_ratio    = (edu_verified / edu_total) if edu_total > 0 else 0.5
    edu_score    = _clamp((1 - edu_ratio) * 100)

    breakdown["education"] = {
        "score": edu_score,
        "weight": _COMPONENT_WEIGHTS["education"],
        "verified": edu_verified,
        "total": edu_total,
        "reasoning": f"{edu_verified}/{edu_total} education records verified.",
    }

    # ── Fraud indicators (25 %) ─────────────────────────────────────────────
    fraud_score = 0
    for flag in fraud_flags:
        severity = flag.severity if hasattr(flag, "severity") else flag.get("severity", "low")
        fraud_score += _FLAG_SEVERITY_WEIGHTS.get(severity, 8)
    fraud_score = _clamp(fraud_score)

    flag_types = [
        (flag.flag_type if hasattr(flag, "flag_type") else flag.get("flag_type", ""))
        for flag in fraud_flags
    ]

    breakdown["fraud"] = {
        "score": fraud_score,
        "weight": _COMPONENT_WEIGHTS["fraud"],
        "flag_count": len(fraud_flags),
        "flag_types": flag_types,
        "reasoning": f"{len(fraud_flags)} fraud indicator(s) detected.",
    }

    # ── Public records (10 %) ───────────────────────────────────────────────
    pub_score = 50 if public_record_matches else 0
    breakdown["public_records"] = {
        "score": pub_score,
        "weight": _COMPONENT_WEIGHTS["public_records"],
        "match_count": len(public_record_matches),
        "reasoning": (
            "Potential public record match found — manual review required."
            if public_record_matches
            else "No public record matches found."
        ),
    }

    # ── Digital footprint (5 %) — placeholder ──────────────────────────────
    breakdown["digital"] = {
        "score": 0,
        "weight": _COMPONENT_WEIGHTS["digital"],
        "reasoning": "Digital footprint analysis not yet available.",
    }

    # ── Weighted total ──────────────────────────────────────────────────────
    overall = sum(
        v["score"] * v["weight"] for v in breakdown.values()
    )
    overall = _clamp(overall)

    risk_level = (
        "critical" if overall >= 75 else
        "high"     if overall >= 50 else
        "medium"   if overall >= 25 else
        "low"
    )

    # ── AI explanation ──────────────────────────────────────────────────────
    summary_parts = [v["reasoning"] for v in breakdown.values()]
    ai_reasoning = await _generate_reasoning(overall, risk_level, summary_parts)

    # ── Confidence ──────────────────────────────────────────────────────────
    data_completeness = min(1.0, (emp_total + edu_total) / max(1, 3))
    confidence = round(0.60 + data_completeness * 0.35, 2)

    return {
        "overall_score": overall,
        "risk_level": risk_level,
        "breakdown": breakdown,
        "ai_reasoning": ai_reasoning,
        "confidence": confidence,
    }


async def _generate_reasoning(score: int, level: str, summary_parts: list[str]) -> str:
    """Ask LLM to produce a human-readable risk assessment summary."""
    bullets = "\n".join(f"- {p}" for p in summary_parts if p)
    prompt = f"""Write a professional 3-sentence risk assessment for a background verification report.

Risk score: {score}/100 ({level} risk)
Findings:
{bullets}

Rules:
- Be factual and objective.
- Use hedging language: "may indicate", "warrants review", "could not be confirmed".
- Do NOT make definitive statements about guilt or innocence.
- Do NOT recommend hiring or rejection.
- Write in third person about the candidate.
"""
    try:
        return await ainvoke_llm(prompt, task="report")
    except Exception as exc:
        logger.warning("AI reasoning generation failed: %s", exc)
        return (
            f"Overall risk score: {score}/100 ({level}). "
            "Verification completed with the findings noted above. "
            "Please review individual component scores for details."
        )
