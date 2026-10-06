"""Rule-based risk scoring engine for job postings.

Evaluates multiple verification signals (GST, MCA, Udyam, Domain/WHOIS/SSL,
fuzzy name matching, and recruiter behavioral patterns) to assign a cumulative
fraud risk score, identify critical risk factors, and determine the appropriate risk band.
"""

from datetime import datetime
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.utils.recommendations import generate_safety_recommendations

# ---------------------------------------------------------------------------
# Configurable Detection Parameters & Registries
# ---------------------------------------------------------------------------

# Major corporate brands often targeted for recruitment impersonation
CONFIGURABLE_MAJOR_COMPANIES: List[str] = [
    "Microsoft",
    "Google",
    "Amazon",
    "Apple",
    "Meta",
    "TCS",
    "Tata Consultancy Services",
    "Infosys",
    "Wipro",
    "HCL",
    "IBM",
    "Accenture",
    "Cognizant",
    "Deloitte",
    "Tech Mahindra",
    "Capgemini",
    "State Bank of India",
    "SBI",
    "ICICI",
    "HDFC",
    "Reliance",
    "Flipkart",
    "Swiggy",
    "Zomato",
]

# Known official domains for major corporations to corroborate authentic web presence
MAJOR_COMPANY_OFFICIAL_DOMAINS: Dict[str, List[str]] = {
    "microsoft": ["microsoft.com", "msn.com", "azure.com", "windows.com", "linkedin.com"],
    "google": ["google.com", "google.co.in", "alphabet.com"],
    "amazon": ["amazon.com", "amazon.in", "aws.amazon.com"],
    "apple": ["apple.com"],
    "meta": ["meta.com", "facebook.com", "instagram.com"],
    "tcs": ["tcs.com", "tataconsultancy.com", "tata.com"],
    "tata consultancy services": ["tcs.com", "tataconsultancy.com", "tata.com"],
    "infosys": ["infosys.com"],
    "wipro": ["wipro.com"],
    "hcl": ["hcltech.com", "hcl.com"],
    "ibm": ["ibm.com"],
    "accenture": ["accenture.com"],
    "cognizant": ["cognizant.com"],
    "deloitte": ["deloitte.com"],
    "tech mahindra": ["techmahindra.com"],
    "capgemini": ["capgemini.com"],
    "state bank of india": ["sbi.co.in", "onlinesbi.sbi"],
    "sbi": ["sbi.co.in", "onlinesbi.sbi"],
}

# Suspicious, free, or low-cost TLDs commonly abused in disposable job scam portals
SUSPICIOUS_TLDS: List[str] = [
    r"\.xyz$",
    r"\.tk$",
    r"\.ml$",
    r"\.ga$",
    r"\.cf$",
    r"\.gq$",
    r"\.top$",
    r"\.buzz$",
    r"\.club$",
    r"\.work$",
]

# Keywords typical in lookalike or spear-phishing recruitment subdomains
LOOKALIKE_KEYWORDS: List[str] = [
    "careers",
    "career",
    "jobs",
    "job",
    "hiring",
    "recruitment",
    "recruit",
    "apply",
    "official",
    "india",
    "portal",
    "online",
    "internship",
]

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "yahoo.co.in",
    "hotmail.com",
    "outlook.com",
    "rediffmail.com",
    "icloud.com",
    "protonmail.com",
    "zoho.com",
    "aol.com",
    "mail.com",
}

FREE_HOSTING_PATTERNS = [
    r"blogspot\.[a-z.]+",
    r"wixsite\.com",
    r"weebly\.com",
    r"wordpress\.com",
    r"sites\.google\.com",
    r"webflow\.io",
    r"github\.io",
]

RESIDENTIAL_ADDRESS_KEYWORDS = [
    "flat no",
    "flat ",
    "apartment",
    "apt ",
    "residential",
    "housing society",
    "chawl",
    "room no",
    "house no",
]

UPFRONT_FEE_PATTERNS = [
    r"(?:registration|application|internship|training|verification|processing|certificate|placement)\s+fee",
    r"security\s+deposit",
    r"refundable\s+deposit",
    r"laptop\s+(?:deposit|fee|charge)",
    r"documentation\s+charge",
    r"uniform\s+charge",
    r"courier\s+fee",
    r"pay\s+before\s+interview",
    r"mandatory\s+payment",
    r"(?:fee|deposit|charge|amount|pay|fee\s+of|deposit\s+of)\s*(?:of\s*)?(?:₹|rs\.?|inr)\s*[\d,]+",
    r"(?:₹|rs\.?|inr)\s*[\d,]+\s*(?:fee|deposit|charge|to\s+confirm|before|for\s+internship|for\s+registration|registration)",
    r"pay\s+(?:a\s+)?(?:refundable\s+)?(?:registration\s+)?fee",
]

URGENCY_PATTERNS = [
    r"apply\s+within\s+\d+\s+hours?",
    r"within\s+24\s+hours?",
    r"offer\s+expires\s+today",
    r"offer\s+expires\s+in",
    r"limited\s+seats?",
    r"limited\s+slots?",
    r"immediate\s+joining",
    r"pay\s+now",
    r"pay\s+immediately",
    r"last\s+chance",
    r"respond\s+immediately",
    r"complete\s+payment\s+today",
    r"selection\s+will\s+be\s+cancelled",
    r"direct\s+selection\s+without\s+interview",
    r"urgent\s+hiring\s+no\s+interview",
]

SENSITIVE_DOC_PATTERNS = [
    r"\baadhaar\b",
    r"\baadhar\b",
    r"\bpan\s+card\b",
    r"\bpan\s+number\b",
    r"\bpan\s+details?\b",
    r"\bbank\s+account\b",
    r"\baccount\s+number\b",
    r"\bdebit\s+card\b",
    r"\bcredit\s+card\b",
    r"\bcard\s+details?\b",
    r"\botp\b",
    r"\bupi\s+pin\b",
    r"\bpassport\b",
    r"\bfull\s+identity\s+documents?\b",
    r"\bsensitive\s+financial\b",
]


def _parse_date_to_days_ago(date_str: str) -> Optional[int]:
    """Parse common date formats and return the number of days elapsed."""
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip().split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            diff = datetime.now() - dt
            return max(0, diff.days)
        except ValueError:
            continue
    return None


def _get_message_text(job: Dict[str, Any]) -> str:
    """Consolidate submitted job message and notes into a normalized lowercase text string."""
    parts = []
    for k in (
        "job_message",
        "message",
        "description",
        "email_body",
        "message_text",
        "fee_details",
        "payment_terms",
        "notes",
    ):
        val = job.get(k)
        if val and isinstance(val, str) and val.strip():
            parts.append(val.strip())
    return " ".join(parts).lower()


def _find_matching_major_company(name: str) -> Optional[str]:
    """Check if a company name or domain references a major recognized brand."""
    if not name or not isinstance(name, str):
        return None
    name_clean = name.strip().lower()
    for major in CONFIGURABLE_MAJOR_COMPANIES:
        m_lower = major.lower()
        # Word boundary match to prevent false positives on substrings
        pattern = r"\b" + re.escape(m_lower) + r"\b"
        if re.search(pattern, name_clean):
            return major
    return None


# ---------------------------------------------------------------------------
# Individual Rule Evaluators
# Each returns: (triggered: bool, weight: int, reason: str)
# ---------------------------------------------------------------------------


def rule_mca_status_inactive(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 1: MCA STATUS = STRIKE OFF / INACTIVE — Weight: +25
    Triggered when MCA/company registry status indicates:
    - Strike Off / Struck Off
    - Dissolved
    - Inactive (if explicitly identified in registry records)
    """
    weight = 25
    mca_status = str(mca.get("status") or "").strip().lower()
    inactive_keywords = [
        "struck off",
        "strike off",
        "dissolved",
        "inactive",
        "under liquidation",
        "amalgamated",
        "dormant",
    ]

    for kw in inactive_keywords:
        if kw in mca_status:
            raw_status = mca.get("status", "Strike Off")
            return (
                True,
                weight,
                f"+25 — MCA entity is inactive or struck off. Registered company status is '{raw_status}'.",
            )

    return (False, weight, "")


rule_mca_status_inactive.rule_id = "mca_struck_off"


def rule_company_name_mismatch(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 2: COMPANY NAME MISMATCH — Weight: +20
    Triggered when the claimed company name does not sufficiently match the MCA registered company name.
    Does NOT trigger when company-name match is strong (score >= 80%).
    """
    weight = 20

    # Explicit flag in job context
    if job.get("name_mismatch") is True:
        return (
            True,
            weight,
            "+20 — Company name discrepancy across sources. Claimed company name does not match the registered MCA entity.",
        )

    # Check fuzzy matching result
    if matching:
        best_match = matching.get("best_match")
        score = float(matching.get("score", 0.0))
        is_no_match = matching.get("no_match", False)

        # Trigger if registry candidate was evaluated but resulted in mismatch (< 80%)
        if best_match is not None and (is_no_match or score < 80.0):
            cand_name = best_match.get("name") or best_match.get("company_name") or "registry record"
            claimed = matching.get("claimed_name") or job.get("company_name") or "Claimed name"
            return (
                True,
                weight,
                f"+20 — Company name discrepancy across sources. Claimed company name ('{claimed}') does not match registered MCA entity '{cand_name}' (similarity: {round(score, 1)}%).",
            )

    return (False, weight, "")


rule_company_name_mismatch.rule_id = "company_name_mismatch"
rule_name_mismatch_across_sources = rule_company_name_mismatch


def rule_major_company_impersonation(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 3: MAJOR-COMPANY IMPERSONATION / LOOKALIKE COMPANY NAME — Weight: +25
    Triggered when:
    - The claimed company name contains or closely resembles a well-known/major company name
    AND
    - The verified corporate entity is an unrelated entity (does not corroborate identity)
    AND/OR
    - The domain appears to imitate the major company's identity (lookalike domain).
    """
    weight = 25
    claimed_name = str(job.get("company_name") or matching.get("claimed_name") or "").strip()
    major_found = _find_matching_major_company(claimed_name)

    if not major_found:
        return (False, weight, "")

    major_lower = major_found.lower()

    # Check if domain is the official domain of this major company
    claimed_dom = str(domain.get("domain") or job.get("claimed_domain") or "").strip().lower()
    dom_clean = re.sub(r"^https?://", "", claimed_dom).split("/")[0]
    official_domains = MAJOR_COMPANY_OFFICIAL_DOMAINS.get(major_lower, [])
    is_domain_official = False
    if dom_clean:
        for off_dom in official_domains:
            if dom_clean == off_dom or dom_clean.endswith("." + off_dom):
                is_domain_official = True
                break

    # If the domain is officially verified as the real company's domain, it is NOT an impersonation
    if is_domain_official:
        return (False, weight, "")

    # Check if official registry records corroborate the major brand
    best_match = matching.get("best_match") if isinstance(matching.get("best_match"), dict) else {}
    best_match_name = str(best_match.get("name") or best_match.get("company_name") or "").lower()
    mca_name = str(mca.get("company_name") or "").lower()
    gst_name = str(gst.get("legal_name") or gst.get("trade_name") or "").lower()

    score = float(matching.get("score", 0.0))
    no_match = matching.get("no_match", False)

    # Check if any registry record matched with high score and contains the brand
    is_registry_corroborated = (
        (major_lower in best_match_name and (score >= 80.0 or not no_match))
        or (major_lower in mca_name and not mca.get("error") and (score >= 80.0 or not no_match))
        or (major_lower in gst_name and not gst.get("error") and (score >= 80.0 or not no_match))
    )

    if is_registry_corroborated:
        return (False, weight, "")

    # Check if lookalike domain is present or entity is mismatched
    is_lookalike_domain = False
    if dom_clean and not is_domain_official:
        if major_lower in dom_clean and any(kw in dom_clean for kw in LOOKALIKE_KEYWORDS):
            is_lookalike_domain = True

    # Check if verified entity is a different/unrelated entity
    entity_is_unrelated = False
    if (mca_name and major_lower not in mca_name) or (best_match_name and major_lower not in best_match_name):
        entity_is_unrelated = True
    elif no_match or score < 80.0:
        entity_is_unrelated = True

    if is_lookalike_domain or entity_is_unrelated:
        return (
            True,
            weight,
            f"+25 — Possible major-company impersonation. The claimed organization appears associated with a major company ('{major_found}'), but the verified corporate entity does not corroborate that identity.",
        )

    return (False, weight, "")


rule_major_company_impersonation.rule_id = "major_company_impersonation"


def rule_suspicious_lookalike_domain(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 4: SUSPICIOUS LOOKALIKE DOMAIN — Weight: +20
    Triggered when the claimed domain appears designed to imitate a known company's official domain:
    - Major company name inside the domain
    - Additional keywords like careers, jobs, hiring, apply, india, etc.
    - Domain does not correspond to the verified company's official identity.
    """
    weight = 20
    dom_str = str(
        domain.get("domain") or job.get("claimed_domain") or job.get("website") or ""
    ).strip().lower()

    if not dom_str:
        return (False, weight, "")

    # Remove protocol if present
    dom_clean = re.sub(r"^https?://", "", dom_str).split("/")[0]

    # Find if domain references a major company
    major_in_dom = None
    for major in CONFIGURABLE_MAJOR_COMPANIES:
        m_lower = major.lower()
        if m_lower in dom_clean:
            major_in_dom = m_lower
            break

    if not major_in_dom:
        return (False, weight, "")

    # Check if this is an official domain
    official_domains = MAJOR_COMPANY_OFFICIAL_DOMAINS.get(major_in_dom, [])
    for off in official_domains:
        if dom_clean == off or dom_clean.endswith("." + off):
            return (False, weight, "")

    # Check for presence of lookalike recruitment words
    has_lookalike_word = any(kw in dom_clean for kw in LOOKALIKE_KEYWORDS)
    if has_lookalike_word:
        return (
            True,
            weight,
            f"+20 — Suspicious lookalike domain. The domain '{dom_clean}' appears designed to resemble a company or recruitment brand but could not be corroborated as its official domain.",
        )

    return (False, weight, "")


rule_suspicious_lookalike_domain.rule_id = "suspicious_lookalike_domain"


def rule_suspicious_or_free_tld(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 5: SUSPICIOUS / FREE TLD — Weight: +15
    Triggered when the domain uses a suspicious or commonly abused free/low-cost TLD (.xyz, .tk, .ml, .ga, etc.).
    This rule alone NEVER classifies a company as fraudulent.
    """
    weight = 15
    dom_str = str(
        domain.get("domain") or job.get("claimed_domain") or job.get("website") or ""
    ).strip().lower()

    if not dom_str:
        return (False, weight, "")

    dom_clean = re.sub(r"^https?://", "", dom_str).split("/")[0]

    for pattern in SUSPICIOUS_TLDS:
        if re.search(pattern, dom_clean):
            return (
                True,
                weight,
                f"+15 — Suspicious domain extension. The domain '{dom_clean}' uses a TLD that requires additional verification.",
            )

    return (False, weight, "")


rule_suspicious_or_free_tld.rule_id = "suspicious_or_free_tld"


def rule_ssl_unavailable_or_invalid(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 6: SSL UNAVAILABLE / INVALID — Weight: +10
    Triggered when domain verification explicitly reports:
    - SSL unavailable
    - SSL invalid
    - SSL expired
    - SSL self-signed
    - HTTPS verification failure
    Do NOT trigger when SSL is valid or when domain was omitted.
    """
    weight = 10
    dom_str = str(domain.get("domain") or job.get("claimed_domain") or "").strip()

    # Do not penalize if no domain was provided
    if not dom_str:
        return (False, weight, "")

    ssl_status = str(domain.get("ssl_status") or "").strip().lower()
    has_ssl = domain.get("has_ssl")
    ssl_error = str(domain.get("ssl_error") or "").strip().lower()

    invalid_indicators = [
        "unavailable",
        "invalid",
        "expired",
        "self-signed",
        "self_signed",
        "failed",
        "error",
    ]

    is_invalid = any(ind in ssl_status for ind in invalid_indicators) or (has_ssl is False) or bool(ssl_error)

    # Valid SSL must never trigger
    if ssl_status == "valid" or has_ssl is True:
        return (False, weight, "")

    if is_invalid and ssl_status:
        return (
            True,
            weight,
            "+10 — SSL verification failed or is unavailable for the supplied domain.",
        )

    return (False, weight, "")


rule_ssl_unavailable_or_invalid.rule_id = "ssl_unavailable_or_invalid"


def rule_upfront_payment_demanded(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 7: UPFRONT PAYMENT / FEE REQUEST — Weight: +35
    Triggered when the submitted job/internship message contains an upfront payment request.
    Does NOT trigger merely because a salary or stipend amount is mentioned.
    """
    weight = 35
    if job.get("upfront_fee_demanded") is True:
        return (True, weight, "+35 — Upfront payment requested before employment/internship.")

    text_corpus = _get_message_text(job)
    if not text_corpus:
        return (False, weight, "")

    for pattern in UPFRONT_FEE_PATTERNS:
        if re.search(pattern, text_corpus):
            return (
                True,
                weight,
                "+35 — Upfront payment requested before employment/internship.",
            )

    return (False, weight, "")


rule_upfront_payment_demanded.rule_id = "upfront_payment_demanded"


def rule_urgency_pressure_tactics(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 8: URGENCY / PRESSURE TACTICS — Weight: +10
    Triggered when communication contains pressure tactics or artificial deadlines.
    Does NOT trigger just because a joining date is mentioned.
    """
    weight = 10
    if job.get("urgency_tactics") is True:
        return (
            True,
            weight,
            "+10 — Urgency or pressure tactics detected in the job/internship communication.",
        )

    text_corpus = _get_message_text(job)
    if not text_corpus:
        return (False, weight, "")

    for pattern in URGENCY_PATTERNS:
        if re.search(pattern, text_corpus):
            return (
                True,
                weight,
                "+10 — Urgency or pressure tactics detected in the job/internship communication.",
            )

    return (False, weight, "")


rule_urgency_pressure_tactics.rule_id = "urgency_pressure_tactics"


def rule_sensitive_documents_requested(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Rule 9: SENSITIVE DOCUMENTS REQUESTED BEFORE VERIFICATION — Weight: +15
    Triggered when the message asks for sensitive personal or financial information
    (Aadhaar, PAN, bank account details, OTP, etc.) before the job has been verified.
    """
    weight = 15
    if job.get("sensitive_documents_requested") is True:
        return (
            True,
            weight,
            "+15 — Sensitive personal or financial information requested before verification.",
        )

    text_corpus = _get_message_text(job)
    if not text_corpus:
        return (False, weight, "")

    for pattern in SENSITIVE_DOC_PATTERNS:
        if re.search(pattern, text_corpus):
            return (
                True,
                weight,
                "+15 — Sensitive personal or financial information requested before verification.",
            )

    return (False, weight, "")


rule_sensitive_documents_requested.rule_id = "sensitive_documents_requested"


def rule_free_hosting_subdomain(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Detection of free website builders / hosted subdomains — Weight: +20
    Legitimate corporate entities do not host recruitment portals on free website builders
    (e.g., Blogspot, Wix, Weebly, WordPress.com).
    """
    weight = 20
    dom_str = str(
        domain.get("domain") or job.get("claimed_domain") or job.get("website") or ""
    ).strip().lower()

    if not dom_str:
        return (False, weight, "")

    for pattern in FREE_HOSTING_PATTERNS:
        if re.search(pattern, dom_str):
            return (
                True,
                weight,
                f"Website '{dom_str}' uses a free website builder / hosted subdomain instead of an independent corporate domain.",
            )

    return (False, weight, "")


def rule_free_hosting_or_tld(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """Legacy backward-compatible wrapper for free hosting or TLD check."""
    t1, w1, r1 = rule_free_hosting_subdomain(gst, mca, udyam, domain, matching, job)
    if t1:
        return t1, w1, r1
    t2, w2, r2 = rule_suspicious_or_free_tld(gst, mca, udyam, domain, matching, job)
    if t2:
        return t2, w2, r2
    return (False, 20, "")


def rule_no_registry_match(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    No registry match found at all for company name — Weight: +40
    Triggered when no official registry (MCA, GST, Udyam) confirms entity existence.
    """
    weight = 40
    mca_valid = bool(mca.get("cin") and mca.get("status") and not mca.get("error"))
    gst_valid = bool(gst.get("legal_name") and gst.get("status") and not gst.get("error"))
    udyam_valid = bool(udyam.get("registered") is True and not udyam.get("error"))

    if not mca_valid and not gst_valid and not udyam_valid:
        if matching.get("no_match") is not False:
            claimed = job.get("company_name") or matching.get("claimed_name") or "Claimed company"
            return (
                True,
                weight,
                f"No official government registry match (MCA, GST, or Udyam) found for '{claimed}'.",
            )

    return (False, weight, "")


rule_no_registry_match.rule_id = "no_registry_match"


def rule_domain_age_under_3_months(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Domain age < 3 months for a company claiming to be established — Weight: +20
    """
    weight = 20
    age_days = domain.get("domain_age_days")
    claims_established = job.get("claims_established", True)

    if age_days is not None and age_days < 90 and claims_established:
        dom_name = domain.get("domain") or "Company domain"
        return (
            True,
            weight,
            f"Domain '{dom_name}' is only {age_days} days old (< 3 months) despite claiming to be an established entity.",
        )

    return (False, weight, "")


rule_domain_age_under_3_months.rule_id = "domain_age_under_3_months"


def rule_personal_email_contact(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Contact via personal email (gmail/yahoo/outlook) instead of company domain — Weight: +15
    """
    weight = 15
    if job.get("uses_personal_email") is True:
        return (
            True,
            weight,
            "Recruiter communication originated from a free/personal email address.",
        )

    contact_email = str(job.get("contact_email") or job.get("recruiter_email") or "").strip().lower()
    if "@" in contact_email:
        domain_part = contact_email.split("@")[-1]
        if domain_part in FREE_EMAIL_DOMAINS:
            return (
                True,
                weight,
                f"Contact email '{contact_email}' uses a personal email provider (@{domain_part}) instead of an official company domain.",
            )

    return (False, weight, "")


rule_personal_email_contact.rule_id = "personal_email_contact"


def rule_gst_status_cancelled(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    GST status = cancelled / suspended — Weight: +15
    """
    weight = 15
    gst_status = str(gst.get("status") or "").strip().lower()
    invalid_gst_keywords = ["cancelled", "suspended", "inactive", "revoked"]

    for kw in invalid_gst_keywords:
        if kw in gst_status:
            return (
                True,
                weight,
                f"GST registration status is '{gst.get('status')}' (invalid/inactive tax registration).",
            )

    return (False, weight, "")


rule_gst_status_cancelled.rule_id = "gst_status_cancelled"


def rule_address_mismatch(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Address mismatch (registered vs claimed) — Weight: +10 standard / +15 residential shell vs enterprise HQ
    """
    reg_addr = str(
        mca.get("registered_address")
        or mca.get("registered_office_address")
        or gst.get("address")
        or gst.get("principal_place_of_business")
        or ""
    ).lower()

    scale = str(job.get("company_scale") or "").strip().lower()
    claims_enterprise_hq = (
        job.get("claims_mnc") is True
        or job.get("claims_global") is True
        or scale in ("mnc", "multinational", "large enterprise", "global")
        or any(
            kw in str(job.get("claimed_address", "")).lower()
            for kw in ("15 countries", "countries", "global", "offices in", "multinational")
        )
        or any(
            kw in str(job.get("description", "")).lower()
            for kw in ("15 countries", "countries", "global", "multinational")
        )
    )

    is_residential = (
        job.get("residential_address") is True
        or any(rw in reg_addr for rw in RESIDENTIAL_ADDRESS_KEYWORDS)
    )

    if is_residential and claims_enterprise_hq:
        return (
            True,
            15,
            "Registered address in official records appears to be a residential flat/shell address despite claims of being a global or multinational enterprise HQ.",
        )

    if job.get("address_mismatch") is True:
        return (
            True,
            10,
            "Claimed company location conflicts with registered address in government databases.",
        )

    claimed_state = str(job.get("claimed_state") or job.get("state") or "").strip().lower()
    registered_state = str(gst.get("state") or mca.get("company_state_code") or "").strip().lower()

    if claimed_state and registered_state and claimed_state != registered_state:
        if claimed_state not in registered_state and registered_state not in claimed_state:
            return (
                True,
                10,
                f"Claimed office state ('{claimed_state.title()}') does not match registered state ('{registered_state.title()}').",
            )

    return (False, 10, "")


rule_address_mismatch.rule_id = "address_mismatch"


def rule_entity_incorporation_vs_claimed_scale(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Entity incorporation age vs claimed enterprise scale contradiction — Weight: +25
    """
    weight = 25
    inc_date_str = str(
        mca.get("incorporation_date")
        or mca.get("company_registration_date")
        or mca.get("date_of_registration")
        or ""
    ).strip()

    age_days = mca.get("entity_age_days") or job.get("incorporation_age_days")
    if age_days is None and inc_date_str:
        age_days = _parse_date_to_days_ago(inc_date_str)

    scale = str(job.get("company_scale") or "").strip().lower()
    claims_mnc = (
        job.get("claims_mnc") is True
        or job.get("claims_global") is True
        or scale in ("mnc", "multinational", "large enterprise", "global", "fortune 500")
    )

    text_corpus = " ".join(
        str(job.get(k, ""))
        for k in ("description", "claimed_address", "notes", "claimed_scale")
    ).lower()

    mnc_text_indicator = any(
        kw in text_corpus
        for kw in (
            "offices in",
            "fortune 500",
            "multinational",
            "global mnc",
            "leading mnc",
            "countries",
        )
    )

    is_recently_incorporated = (
        job.get("entity_recently_incorporated") is True
        or job.get("incorporation_contradicts_scale") is True
        or (age_days is not None and age_days < 365)
    )

    if (claims_mnc or mnc_text_indicator) and is_recently_incorporated:
        days_desc = f"{age_days} days ago" if age_days is not None else "recently"
        date_desc = f" ({inc_date_str})" if inc_date_str else ""
        return (
            True,
            weight,
            f"Company claims to be an established MNC/global enterprise, but official MCA records show entity was incorporated {days_desc}{date_desc} (< 1 year).",
        )

    return (False, weight, "")


rule_entity_incorporation_vs_claimed_scale.rule_id = "entity_incorporation_vs_claimed_scale"


def rule_unofficial_channels_only(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Posting/communication only on unofficial channels (WhatsApp, Telegram) — Weight: +10
    """
    weight = 10
    channel = str(job.get("communication_channel") or job.get("posting_channel") or "").strip().lower()
    unofficial_channels = ["whatsapp", "telegram", "signal", "sms", "direct message"]

    if job.get("unofficial_channel_only") is True or any(c in channel for c in unofficial_channels):
        if job.get("has_official_careers_page") is False or not job.get("official_careers_url"):
            return (
                True,
                weight,
                "Job application and communication conducted exclusively via unofficial channels (e.g. WhatsApp, Telegram) with no verified careers portal.",
            )

    return (False, weight, "")


rule_unofficial_channels_only.rule_id = "unofficial_channels_only"


def rule_no_linkedin_presence_for_mnc(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    No LinkedIn presence for a company claiming to be an MNC — Weight: +10
    """
    weight = 10
    scale = str(job.get("company_scale") or "").strip().lower()
    claims_mnc = job.get("claims_mnc") is True or scale in ("mnc", "multinational", "large enterprise")
    has_linkedin = job.get("has_linkedin_presence")

    if claims_mnc and has_linkedin is False:
        return (
            True,
            weight,
            "Employer claims to be a multinational corporation (MNC) but lacks any verifiable LinkedIn company presence.",
        )

    return (False, weight, "")


rule_no_linkedin_presence_for_mnc.rule_id = "no_linkedin_presence_for_mnc"


def rule_udyam_absent_for_small_business(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Udyam absent for claimed small business — Weight: +5 (suppressed when MCA + GST verified active)
    """
    weight = 5
    scale = str(job.get("company_scale") or "").strip().lower()
    claims_small = job.get("claims_msme") is True or scale in ("small", "micro", "msme", "local business")

    udyam_registered = udyam.get("registered") is True

    mca_status = str(mca.get("status") or "").strip().lower()
    mca_active = bool(mca.get("cin") and mca_status == "active" and not mca.get("error"))

    gst_status = str(gst.get("status") or "").strip().lower()
    gst_active = bool(gst.get("legal_name") and gst_status == "active" and not gst.get("error"))

    if mca_active and gst_active:
        return (False, 0, "")

    if claims_small and not udyam_registered:
        return (
            True,
            weight,
            "Employer claims to be a small/local MSME enterprise, but no active Udyam registration was confirmed.",
        )

    return (False, weight, "")


rule_udyam_absent_for_small_business.rule_id = "udyam_absent_for_small_business"


def rule_udyam_absent_for_large_mnc(
    gst: Dict[str, Any],
    mca: Dict[str, Any],
    udyam: Dict[str, Any],
    domain: Dict[str, Any],
    matching: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[bool, int, str]:
    """
    Udyam absent for large MNC — Weight: 0 (large enterprises are ineligible for MSME)
    """
    scale = str(job.get("company_scale") or "").strip().lower()
    claims_mnc = job.get("claims_mnc") is True or scale in ("mnc", "multinational", "large", "enterprise")

    udyam_registered = udyam.get("registered") is True

    if claims_mnc and not udyam_registered:
        return (
            False,
            0,
            "Absence of Udyam registration is expected for large multinational corporations (zero risk).",
        )

    return (False, 0, "")


rule_udyam_absent_for_large_mnc.rule_id = "udyam_absent_for_large_mnc"


# ---------------------------------------------------------------------------
# Rule Engine Registry
# ---------------------------------------------------------------------------

ALL_RULES: List[Callable[..., Tuple[bool, int, str]]] = [
    rule_mca_status_inactive,
    rule_company_name_mismatch,
    rule_major_company_impersonation,
    rule_suspicious_lookalike_domain,
    rule_suspicious_or_free_tld,
    rule_ssl_unavailable_or_invalid,
    rule_upfront_payment_demanded,
    rule_urgency_pressure_tactics,
    rule_sensitive_documents_requested,
    rule_free_hosting_subdomain,
    rule_domain_age_under_3_months,
    rule_personal_email_contact,
    rule_gst_status_cancelled,
    rule_address_mismatch,
    rule_entity_incorporation_vs_claimed_scale,
    rule_unofficial_channels_only,
    rule_no_linkedin_presence_for_mnc,
    rule_no_registry_match,
    rule_udyam_absent_for_small_business,
    rule_udyam_absent_for_large_mnc,
]


def determine_risk_band(score: int, risk_level: Optional[str] = None) -> str:
    """
    Determine qualitative risk band description based on score and overridden risk level.
    """
    if risk_level:
        lvl = risk_level.upper()
        if lvl == "HIGH":
            return "High risk (strong warning to user)"
        elif lvl == "MEDIUM":
            return "Medium risk (manual review suggested)"
        elif lvl == "LOW":
            return "Low risk"

    if score <= 20:
        return "Low risk"
    elif score <= 50:
        return "Medium risk (manual review suggested)"
    else:
        return "High risk (strong warning to user)"


def evaluate_rules(
    gst_result: Optional[Dict[str, Any]] = None,
    mca_result: Optional[Dict[str, Any]] = None,
    udyam_result: Optional[Dict[str, Any]] = None,
    domain_result: Optional[Dict[str, Any]] = None,
    matching_result: Optional[Dict[str, Any]] = None,
    job_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run the risk scoring rule engine across all verification results.

    Evaluates every rule independently, accumulates triggered weights without double-counting,
    applies critical-risk overrides, and formats explainable structured reasons.

    Returns:
        {
            "risk_score": int,
            "risk_level": "LOW" | "MEDIUM" | "HIGH",
            "risk_band": str,
            "reasons": List[Dict[str, Any]],  # Structured objects with rule, score, reason
            "triggered_reasons": List[str],    # Formatted explanation strings
            "triggered_rules": List[Dict[str, Any]],
            "total_rules_evaluated": int
        }
    """
    gst = gst_result if isinstance(gst_result, dict) else {}
    mca = mca_result if isinstance(mca_result, dict) else {}
    udyam = udyam_result if isinstance(udyam_result, dict) else {}
    domain = domain_result if isinstance(domain_result, dict) else {}
    matching = matching_result if isinstance(matching_result, dict) else {}
    job = job_details if isinstance(job_details, dict) else {}

    risk_score = 0
    triggered_rules: List[Dict[str, Any]] = []
    triggered_reasons: List[str] = []
    reasons: List[Dict[str, Any]] = []

    for rule_fn in ALL_RULES:
        try:
            triggered, weight, reason = rule_fn(gst, mca, udyam, domain, matching, job)
            if triggered and weight > 0:
                risk_score += weight
                rule_name = getattr(rule_fn, "rule_id", rule_fn.__name__.replace("rule_", ""))
                rule_dict = {
                    "rule": rule_name,
                    "score": weight,
                    "weight": weight,
                    "reason": reason,
                }
                triggered_rules.append(rule_dict)
                reasons.append(
                    {
                        "rule": rule_name,
                        "score": weight,
                        "reason": reason,
                    }
                )
                if reason:
                    triggered_reasons.append(reason)
        except Exception:
            # Prevent any single rule failure from breaking the evaluation
            continue

    # Determine base risk level from numeric score:
    # 0–20 = LOW, 21–50 = MEDIUM, 51+ = HIGH
    if risk_score <= 20:
        risk_level = "LOW"
    elif risk_score <= 50:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    # Critical-Risk Overrides:
    # Condition A: MCA inactive/struck off + name mismatch
    triggered_rule_names = {r["rule"] for r in triggered_rules}
    mca_inactive_triggered = bool(
        {"mca_struck_off", "mca_status_inactive"} & triggered_rule_names
    )
    name_mismatch_triggered = bool(
        {"company_name_mismatch", "name_mismatch_across_sources"} & triggered_rule_names
    )

    # Condition B: Major-company impersonation + name mismatch
    impersonation_triggered = "major_company_impersonation" in triggered_rule_names

    if (mca_inactive_triggered and name_mismatch_triggered) or (
        impersonation_triggered and name_mismatch_triggered
    ):
        risk_level = "HIGH"

    risk_band = determine_risk_band(risk_score, risk_level=risk_level)

    safety_recommendations = generate_safety_recommendations(
        risk_level=risk_level,
        triggered_rules=triggered_rules,
        job_details=job,
        risk_score=risk_score,
    )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_band": risk_band,
        "reasons": reasons,
        "triggered_reasons": triggered_reasons,
        "triggered_rules": triggered_rules,
        "total_rules_evaluated": len(ALL_RULES),
        "safety_recommendations": safety_recommendations,
    }
