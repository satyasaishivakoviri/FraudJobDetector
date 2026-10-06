"""Dynamic Safety Recommendations Engine for FraudJobDetector.

Synthesizes tailored, actionable security recommendations based on detected
risk signals (statutory status, brand impersonation, lookalike domains,
financial requests, urgency, and sensitive document demands).
"""

import re
from typing import Any, Dict, List, Optional


# Regex patterns to detect requests for financial information in job communications
FINANCIAL_INFO_PATTERNS: List[str] = [
    r"\bbank\s+account\b",
    r"\baccount\s+number\b",
    r"\baccount\s+no\b",
    r"\bbank\s+details?\b",
    r"\bdebit\s+card\b",
    r"\bcredit\s+card\b",
    r"\bcard\s+number\b",
    r"\bcard\s+details?\b",
    r"\bcvv\b",
    r"\botp\b",
    r"\bone\s+time\s+password\b",
    r"\bupi\b",
    r"\bupi\s+pin\b",
    r"\bupi\s+id\b",
    r"\bnet\s*banking\b",
    r"\binternet\s+banking\b",
    r"\bpin\s+number\b",
    r"\batm\s+pin\b",
    r"\bfinancial\s+credentials?\b",
    r"\bcancelled\s+cheque\b",
]

# Standard default recommendations shown when no specific risk signals are triggered
DEFAULT_RECOMMENDATIONS: List[str] = [
    "Verify the employer using its official website.",
    "Confirm the recruiter's identity independently.",
    "Do not pay unexpected recruitment or internship fees.",
    "Avoid sharing sensitive personal or financial information until verification is complete.",
    "Be cautious with links and documents received from unknown recruiters.",
]


def _extract_text_corpus(job_details: Optional[Dict[str, Any]]) -> str:
    """Extract and consolidate text fields from job details for heuristic matching."""
    if not job_details or not isinstance(job_details, dict):
        return ""
    parts: List[str] = []
    for key in (
        "job_message",
        "message",
        "description",
        "email_body",
        "message_text",
        "fee_details",
        "payment_terms",
        "notes",
    ):
        val = job_details.get(key)
        if val and isinstance(val, str) and val.strip():
            parts.append(val.strip())
    return " ".join(parts).lower()


def _has_financial_info_request(job_details: Optional[Dict[str, Any]], text_corpus: str) -> bool:
    """Check if the job details or message text contain financial information requests."""
    if not job_details:
        job_details = {}
    if job_details.get("financial_info_requested") or job_details.get("bank_details_requested"):
        return True
    if text_corpus:
        for pattern in FINANCIAL_INFO_PATTERNS:
            if re.search(pattern, text_corpus):
                return True
    return False


def generate_safety_recommendations(
    risk_level: str,
    triggered_rules: List[Dict[str, Any]],
    job_details: Optional[Dict[str, Any]] = None,
    risk_score: int = 0,
) -> List[str]:
    """
    Generate dynamic, contextual safety recommendations based on triggered risk signals.

    Args:
        risk_level: "LOW" | "MEDIUM" | "HIGH"
        triggered_rules: List of rule dicts (e.g. [{"rule": "...", "score": ...}])
        job_details: Optional dictionary containing job message, domain, emails, etc.
        risk_score: Cumulative fraud risk score

    Returns:
        List of actionable recommendation strings, ordered by priority with deduplication.
    """
    lvl = (risk_level or "LOW").upper()
    job = job_details if isinstance(job_details, dict) else {}
    text_corpus = _extract_text_corpus(job)

    # Extract all triggered rule identifiers
    rule_ids = set()
    for r in triggered_rules:
        if isinstance(r, dict) and "rule" in r:
            rule_ids.add(r["rule"])
        elif isinstance(r, str):
            rule_ids.add(r)

    recommendations: List[str] = []

    # 1. UPFRONT PAYMENT DETECTED
    if (
        "upfront_payment_demanded" in rule_ids
        or "upfront_payment" in rule_ids
        or job.get("upfront_fee_demanded") is True
    ):
        recommendations.append(
            "Do not pay registration, verification, training, placement, or internship fees before independently verifying the employer."
        )

    # 2. BANK / FINANCIAL INFORMATION REQUESTED
    if _has_financial_info_request(job, text_corpus):
        recommendations.append(
            "Do not share bank credentials, OTPs, PINs, or payment information with the recruiter."
        )

    # 3. SENSITIVE DOCUMENTS REQUESTED
    if (
        "sensitive_documents_requested" in rule_ids
        or job.get("sensitive_documents_requested") is True
    ):
        recommendations.append(
            "Do not send sensitive identity documents until the employer and job opportunity have been independently verified."
        )

    # 4. COMPANY NAME MISMATCH
    if (
        "company_name_mismatch" in rule_ids
        or "name_mismatch_across_sources" in rule_ids
        or job.get("name_mismatch") is True
    ):
        recommendations.append(
            "Verify the employer using its official website and confirm that the legal company name matches the organization offering the job."
        )

    # 5. POSSIBLE MAJOR COMPANY IMPERSONATION
    if "major_company_impersonation" in rule_ids:
        recommendations.append(
            "If the recruiter claims to represent a major company, contact that company through contact information obtained independently from its official website."
        )

    # 6. SUSPICIOUS DOMAIN / LOOKALIKE DOMAIN
    if (
        "suspicious_lookalike_domain" in rule_ids
        or "suspicious_or_free_tld" in rule_ids
        or "free_hosting_subdomain" in rule_ids
        or "free_hosting_or_tld" in rule_ids
    ):
        recommendations.append(
            "Do not rely on links provided by the recruiter. Open the company's official website separately and verify the recruitment page and domain."
        )

    # 7. MCA STRIKE OFF / INACTIVE
    if (
        "mca_struck_off" in rule_ids
        or "mca_status_inactive" in rule_ids
    ):
        recommendations.append(
            "The registered company identified by the verification system is inactive or struck off. Verify the legal employer independently before proceeding."
        )

    # 8. URGENCY / PRESSURE TACTICS
    if (
        "urgency_pressure_tactics" in rule_ids
        or "urgency_detected" in rule_ids
        or job.get("urgency_tactics") is True
    ):
        recommendations.append(
            "Do not make payments or share personal information because of time pressure. Take time to independently verify the opportunity."
        )

    # 9. PERSONAL EMAIL DETECTED
    if (
        "personal_email_contact" in rule_ids
        or "personal_email_detected" in rule_ids
        or job.get("uses_personal_email") is True
    ):
        recommendations.append(
            "Verify the recruiter's identity through the company's official website rather than relying only on a personal email address."
        )

    # For HIGH risk reports: ensure independent contact recommendation is present
    if lvl == "HIGH":
        contact_rec = "Contact the company through independently obtained contact information."
        if contact_rec not in recommendations:
            recommendations.append(contact_rec)

    # If no specific risk rules triggered, or for clean LOW-risk assessments, return standard guidelines
    if not recommendations or lvl == "LOW":
        recommendations = list(DEFAULT_RECOMMENDATIONS)

    # Deduplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for item in recommendations:
        clean_item = item.strip()
        if clean_item and clean_item not in seen:
            seen.add(clean_item)
            deduped.append(clean_item)

    return deduped
