"""Reusable Dynamic Safety Recommendations Engine for FraudJobDetector.

Evaluates detected risk signals across statutory verifications, brand impersonation,
domain integrity, payment requests, urgency tactics, personal recruiter emails,
and sensitive document requests to produce prioritized, actionable guidance.
"""

import re
from typing import Any, Dict, List, Optional


def generate_safety_recommendations(verification_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generates actionable, structured safety recommendations based strictly on detected
    verification signals and risk indicators. Does not create a separate scoring system.

    Args:
        verification_result: Dictionary containing risk_score, risk_level, triggered_rules,
                             reasons, mca_result, gst_result, domain_result, matching_result,
                             job_details, etc.

    Returns:
        List of structured recommendation dicts:
        [
            {
                "type": "payment" | "sensitive_info" | "company_mismatch" | "impersonation" |
                        "suspicious_domain" | "urgency" | "personal_email" | "mca_status" | "general",
                "title": str,
                "message": str,
                "priority": "high" | "medium" | "low"
            }
        ]
    """
    if not verification_result or not isinstance(verification_result, dict):
        return [
            {
                "type": "general",
                "title": "Basic verification completed",
                "message": "Continue to independently verify the employer and offer before sharing sensitive information or making payments.",
                "priority": "low",
            }
        ]

    recommendations: List[Dict[str, Any]] = []
    seen_types = set()

    # Extract relevant data from verification result
    risk_level = str(verification_result.get("risk_level", "LOW")).upper()
    triggered_rules = verification_result.get("triggered_rules", []) or []
    reasons = verification_result.get("reasons", []) or []
    rule_keys = {r.get("rule", "") for r in triggered_rules if isinstance(r, dict)}

    # Gather consolidated text corpus (reasons, job message, notes)
    text_corpus_parts = []
    for r in reasons:
        if isinstance(r, str):
            text_corpus_parts.append(r)
        elif isinstance(r, dict):
            text_corpus_parts.append(r.get("reason", "") or r.get("description", ""))

    job_details = verification_result.get("job_details", {}) or {}
    for key in ("job_message", "description", "notes"):
        val = job_details.get(key)
        if val and isinstance(val, str):
            text_corpus_parts.append(val)

    offer_data = verification_result.get("offer_data", {}) or {}
    if offer_data and isinstance(offer_data, dict):
        for key in ("payment_or_fee", "recruiter_email", "company_name"):
            val = offer_data.get(key)
            if val and isinstance(val, str):
                text_corpus_parts.append(val)

    text_corpus = " ".join(text_corpus_parts).lower()

    # Extract statutory results
    mca = verification_result.get("mca") or verification_result.get("mca_result") or {}
    domain = verification_result.get("domain") or verification_result.get("domain_result") or {}
    matching = verification_result.get("matching_result") or verification_result.get("company_match") or {}

    # -------------------------------------------------------------
    # 1. PAYMENT DETECTED
    # -------------------------------------------------------------
    payment_patterns = [
        r"\b(?:registration|verification|internship|training|placement|application|security|laptop|uniform|documentation)\s+(?:fee|deposit|charge|amount)\b",
        r"\b(?:refundable\s+deposit|security\s+deposit)\b",
        r"\b(?:pay|deposit|transfer)\s+(?:₹|inr|rs\.?)\b",
    ]
    has_payment = (
        "upfront_payment_demanded" in rule_keys
        or "upfront_payment" in rule_keys
        or any(re.search(pat, text_corpus) for pat in payment_patterns)
    )
    if has_payment and "payment" not in seen_types:
        recommendations.append(
            {
                "type": "payment",
                "title": "Payment detected",
                "message": (
                    "Do not pay the requested registration, verification, training, placement, "
                    "internship, or security fee until the employer and request have been independently verified."
                ),
                "priority": "high",
            }
        )
        seen_types.add("payment")

    # -------------------------------------------------------------
    # 2. SENSITIVE INFORMATION REQUESTED
    # -------------------------------------------------------------
    sensitive_patterns = [
        r"\b(?:aadhaar|aadhar|pan\s*card|pan\s*number|passport)\b",
        r"\b(?:bank\s*account|card\s*number|cvv|otp|one[-\s]time\s*password|upi\s*pin|atm\s*pin|net\s*banking|password|authentication\s*credentials?)\b",
    ]
    has_sensitive = (
        "sensitive_documents_requested" in rule_keys
        or "sensitive_credentials_requested" in rule_keys
        or bool(job_details.get("has_sensitive_info"))
        or bool(offer_data.get("has_sensitive_info"))
        or any(re.search(pat, text_corpus) for pat in sensitive_patterns)
    )
    if has_sensitive and "sensitive_info" not in seen_types:
        recommendations.append(
            {
                "type": "sensitive_info",
                "title": "Sensitive information requested",
                "message": (
                    "Do not share sensitive identity documents (Aadhaar, PAN), bank account credentials, "
                    "OTPs, PINs, or payment information until the employer and request have been independently verified."
                ),
                "priority": "high",
            }
        )
        seen_types.add("sensitive_info")

    # -------------------------------------------------------------
    # 3. COMPANY IDENTITY MISMATCH
    # -------------------------------------------------------------
    has_name_mismatch = (
        "company_name_mismatch" in rule_keys
        or (matching.get("no_match") and matching.get("best_match"))
        or (matching.get("score", 100) < 70 and matching.get("best_match"))
    )
    if has_name_mismatch and "company_mismatch" not in seen_types:
        recommendations.append(
            {
                "type": "company_mismatch",
                "title": "Company identity mismatch",
                "message": (
                    "Company name discrepancy detected. Verify the employer's legal registered name through "
                    "an independently accessed official company website or government registry before proceeding."
                ),
                "priority": "high",
            }
        )
        seen_types.add("company_mismatch")

    # -------------------------------------------------------------
    # 4. POSSIBLE COMPANY IMPERSONATION
    # -------------------------------------------------------------
    has_impersonation = (
        "major_company_impersonation" in rule_keys
        or "impersonation" in text_corpus
        or "lookalike" in text_corpus
    )
    if has_impersonation and "impersonation" not in seen_types:
        recommendations.append(
            {
                "type": "impersonation",
                "title": "Possible company impersonation",
                "message": (
                    "Scammers often impersonate reputable corporate brands. Do not rely only on recruiter-provided "
                    "links or contact details; independently navigate to the organization's official verified website."
                ),
                "priority": "high",
            }
        )
        seen_types.add("impersonation")

    # -------------------------------------------------------------
    # 5. SUSPICIOUS DOMAIN / WEBSITE
    # -------------------------------------------------------------
    has_suspicious_domain = (
        "suspicious_lookalike_domain" in rule_keys
        or "suspicious_or_free_tld" in rule_keys
        or "ssl_unavailable_or_invalid" in rule_keys
        or "free_hosting_subdomain" in rule_keys
        or "domain_age_under_3_months" in rule_keys
        or domain.get("status") in {"Suspicious", "Recently Registered", "Invalid / Unavailable"}
    )
    if has_suspicious_domain and "suspicious_domain" not in seen_types:
        recommendations.append(
            {
                "type": "suspicious_domain",
                "title": "Suspicious website/domain",
                "message": (
                    "Avoid entering credentials or sensitive information through the provided link "
                    "until the domain has been independently verified."
                ),
                "priority": "medium",
            }
        )
        seen_types.add("suspicious_domain")

    # -------------------------------------------------------------
    # 6. URGENCY & PRESSURE TACTICS
    # -------------------------------------------------------------
    has_urgency = (
        "urgency_pressure_tactics" in rule_keys
        or "urgency" in rule_keys
        or "guaranteed_selection" in rule_keys
        or any(
            w in text_corpus
            for w in ("immediate joining", "offer expires today", "act fast", "valid till today", "hurry up")
        )
    )
    if has_urgency and "urgency" not in seen_types:
        recommendations.append(
            {
                "type": "urgency",
                "title": "Urgency detected",
                "message": (
                    "Do not let pressure or a short deadline prevent independent verification "
                    "of the employer and offer."
                ),
                "priority": "medium",
            }
        )
        seen_types.add("urgency")

    # -------------------------------------------------------------
    # 7. PERSONAL / FREE EMAIL ADDRESS
    # -------------------------------------------------------------
    recruiter_email = str(
        job_details.get("contact_email")
        or job_details.get("recruiter_email")
        or offer_data.get("recruiter_email")
        or ""
    ).lower()
    free_providers = ("@gmail.com", "@yahoo.com", "@outlook.com", "@hotmail.com", "@icloud.com", "@rediffmail.com")
    has_personal_email = (
        "personal_email_contact" in rule_keys
        or "personal_email" in rule_keys
        or any(p in recruiter_email for p in free_providers)
        or any(p in text_corpus for p in free_providers)
    )
    if has_personal_email and "personal_email" not in seen_types:
        recommendations.append(
            {
                "type": "personal_email",
                "title": "Personal email address",
                "message": (
                    "Verify the recruiter's identity and company affiliation through an independently "
                    "obtained official company contact channel."
                ),
                "priority": "medium",
            }
        )
        seen_types.add("personal_email")

    # -------------------------------------------------------------
    # 8. MCA INACTIVE / STRUCK OFF
    # -------------------------------------------------------------
    mca_status = str(mca.get("status", "")).strip().lower()
    mca_concerning_statuses = {"strike off", "struck off", "dissolved", "dormant", "inactive"}
    has_mca_concern = (
        "mca_struck_off" in rule_keys
        or any(st in mca_status for st in mca_concerning_statuses)
    )
    if has_mca_concern and "mca_status" not in seen_types:
        recommendations.append(
            {
                "type": "mca_status",
                "title": "Company registration concern",
                "message": (
                    "Registered corporate entity is marked inactive or struck off in statutory registry records. "
                    "Independently verify the company's current legal status before proceeding."
                ),
                "priority": "high",
            }
        )
        seen_types.add("mca_status")

    # -------------------------------------------------------------
    # 9. LOW RISK / NO MAJOR SIGNALS FALLBACK
    # -------------------------------------------------------------
    if len(recommendations) == 0:
        recommendations.append(
            {
                "type": "general",
                "title": "No major warning signals detected",
                "message": (
                    "Continue to independently verify the employer and offer before sharing "
                    "sensitive information or making payments."
                ),
                "priority": "low",
            }
        )

    # Sort recommendations by priority (high > medium > low)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 2))

    return recommendations
