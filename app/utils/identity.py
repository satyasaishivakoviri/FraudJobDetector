"""Company Identity synthesis module for FraudJobDetector.

Evaluates available corporate evidence (MCA, GST, Udyam, Domain WHOIS/SSL,
and Name Matching) to generate a structured corporate identity profile and
calculate an independent Identity Confidence score (0-100%).
"""

from datetime import datetime
import re
from typing import Any, Dict, Optional, Tuple


def calculate_company_age_years(incorporation_date_str: Optional[str]) -> Optional[int]:
    """Calculate company age in years from MCA incorporation date."""
    if not incorporation_date_str or not isinstance(incorporation_date_str, str):
        return None

    cleaned = incorporation_date_str.strip().split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            now = datetime.now()
            years = now.year - dt.year
            if (now.month, now.day) < (dt.month, dt.day):
                years -= 1
            return max(0, years)
        except ValueError:
            continue

    # Attempt regex year extraction if standard formats fail
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", cleaned)
    if year_match:
        try:
            year = int(year_match.group(1))
            now_year = datetime.now().year
            if year <= now_year:
                return now_year - year
        except ValueError:
            pass

    return None


def determine_mca_status(mca: Optional[Dict[str, Any]]) -> str:
    """Determine standardized MCA display status."""
    if mca is None or not isinstance(mca, dict):
        return "Not Available"

    err = str(mca.get("error", "")).lower()
    if err in ("api_timeout", "api_error", "timeout", "error"):
        return "Not Available"
    if err in ("no_match_found", "invalid_input"):
        return "Not Found"

    status_raw = str(mca.get("status", "")).strip().lower()
    if not status_raw and not mca.get("cin"):
        return "Not Found"

    if "active" in status_raw:
        return "Active"
    elif "dormant" in status_raw:
        return "Dormant"
    elif "strike" in status_raw or "struck" in status_raw:
        return "Struck Off"
    elif "inactive" in status_raw or "dissolved" in status_raw or "amalgamated" in status_raw:
        return "Inactive"
    elif status_raw:
        return mca.get("status", "Active")

    return "Not Found"


def determine_gst_status(gst: Optional[Dict[str, Any]], gstin_provided: bool) -> str:
    """Determine standardized GST display status."""
    if not gstin_provided:
        return "Not Provided"

    if gst is None or not isinstance(gst, dict):
        return "Not Available"

    err = str(gst.get("error", "")).lower()
    if err in ("api_timeout", "api_error", "timeout", "error"):
        return "Not Available"
    if err in ("no_match_found", "invalid_gstin_format"):
        return "Not Found"

    status_raw = str(gst.get("status", "")).strip().lower()
    if not status_raw and not gst.get("legal_name") and not gst.get("trade_name"):
        return "Not Found"

    if "active" in status_raw:
        return "Active"
    elif "suspend" in status_raw:
        return "Suspended"
    elif "cancel" in status_raw:
        return "Cancelled"
    elif status_raw:
        return gst.get("status", "Active")

    return "Not Found"


def determine_udyam_status(udyam: Optional[Dict[str, Any]]) -> str:
    """Determine standardized Udyam display status."""
    if udyam is None or not isinstance(udyam, dict):
        return "Not Available"

    err = str(udyam.get("error", "")).lower()
    if err in ("api_timeout", "api_error", "timeout", "error"):
        return "Not Available"

    if udyam.get("registered") is True:
        return "Registered"

    return "Not Found"


def determine_domain_status(domain: Optional[Dict[str, Any]], domain_provided: bool) -> Tuple[str, str]:
    """
    Determine standardized Domain display status and SSL status.
    Returns: (domain_status, ssl_display_status)
    """
    if not domain_provided:
        return ("Not Provided", "Not Available")

    if domain is None or not isinstance(domain, dict):
        return ("Invalid / Unavailable", "Not Available")

    ssl_raw = str(domain.get("ssl_status", "")).strip().lower()
    if ssl_raw == "valid":
        ssl_display = "Valid"
    elif ssl_raw == "expired":
        ssl_display = "Expired"
    elif ssl_raw == "self-signed":
        ssl_display = "Self-Signed"
    else:
        ssl_display = "Not Available"

    age_days = domain.get("domain_age_days")
    is_privacy = domain.get("is_privacy_protected") is True or "privacy" in str(domain.get("registrant_org", "")).lower()

    err = str(domain.get("error", "")).lower()
    if err and not domain.get("domain"):
        return ("Invalid / Unavailable", ssl_display)

    if age_days is not None and age_days < 90:
        return ("Recently Registered", ssl_display)
    elif is_privacy and age_days is None:
        return ("Privacy Protected", ssl_display)
    elif age_days is not None or ssl_display == "Valid":
        return ("Verified", ssl_display)

    return ("Invalid / Unavailable", ssl_display)


def calculate_identity_confidence(
    mca_status: str,
    gst_status: str,
    udyam_status: str,
    domain_status: str,
    similarity_score: float,
    address_match: bool,
) -> int:
    """
    Calculate an independent Corporate Identity Confidence score (0-100%).
    Awards points ONLY when the corresponding verification actually succeeds.
    """
    score = 0

    # 1. MCA successfully verified: +25
    if mca_status == "Active":
        score += 25
    elif mca_status in ("Dormant", "Struck Off", "Inactive"):
        # Real entity exists in registry, though inactive
        score += 10

    # 2. GST successfully verified: +20
    if gst_status == "Active":
        score += 20
    elif gst_status in ("Suspended", "Cancelled"):
        # Real tax record existed
        score += 8

    # 3. Udyam successfully verified: +10
    if udyam_status == "Registered":
        score += 10

    # 4. Domain successfully verified: +15
    if domain_status == "Verified":
        score += 15
    elif domain_status == "Recently Registered":
        # Domain exists, but young
        score += 5
    elif domain_status == "Privacy Protected":
        score += 5

    # 5. Company-name strong match: +20
    if similarity_score >= 80.0:
        score += 20
    elif similarity_score >= 60.0:
        score += 12
    elif similarity_score >= 40.0:
        score += 5

    # 6. Registered address consistency: +10
    if address_match:
        score += 10

    return min(100, max(0, score))


def check_address_consistency(
    mca: Dict[str, Any],
    gst: Dict[str, Any],
    job_details: Dict[str, Any],
) -> bool:
    """Check if address is corroborated across sources."""
    mca_addr = str(mca.get("registered_address") or mca.get("address") or "").lower()
    gst_addr = str(gst.get("principal_address") or gst.get("address") or "").lower()
    job_text = str(job_details.get("description") or job_details.get("notes") or "").lower()

    # If MCA and GST both exist, check if state or pincode matches
    if mca_addr and gst_addr:
        # Check pincode match
        mca_pins = set(re.findall(r"\b[1-9][0-9]{5}\b", mca_addr))
        gst_pins = set(re.findall(r"\b[1-9][0-9]{5}\b", gst_addr))
        if mca_pins and gst_pins and (mca_pins & gst_pins):
            return True

        # Check state match
        states = ["maharashtra", "karnataka", "delhi", "telangana", "gujarat", "tamil nadu", "uttar pradesh", "haryana"]
        for st in states:
            if st in mca_addr and st in gst_addr:
                return True

    # If job text mentions state/city present in MCA address
    if mca_addr and job_text:
        cities = ["mumbai", "bengaluru", "bangalore", "hyderabad", "pune", "delhi", "noida", "gurugram", "gurgaon", "chennai", "ahmedabad", "kolkata"]
        for c in cities:
            if c in mca_addr and c in job_text:
                return True

    return False


def build_company_identity(
    company_name: str,
    mca_result: Optional[Dict[str, Any]],
    gst_result: Optional[Dict[str, Any]],
    udyam_result: Optional[Dict[str, Any]],
    domain_result: Optional[Dict[str, Any]],
    matching_result: Optional[Dict[str, Any]],
    job_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Synthesize complete Company Identity summary object."""
    mca = mca_result if isinstance(mca_result, dict) else {}
    gst = gst_result if isinstance(gst_result, dict) else {}
    udyam = udyam_result if isinstance(udyam_result, dict) else {}
    domain = domain_result if isinstance(domain_result, dict) else {}
    matching = matching_result if isinstance(matching_result, dict) else {}
    job = job_details if isinstance(job_details, dict) else {}

    # 1. MCA Status & Details
    mca_status = determine_mca_status(mca)
    incorp_date = mca.get("incorporation_date") or mca.get("date_of_incorporation")
    company_age = calculate_company_age_years(incorp_date)

    # 2. GST Status & Details
    gstin_provided = bool(job.get("gstin") or gst.get("gstin"))
    gst_status = determine_gst_status(gst, gstin_provided=gstin_provided)

    # 3. Udyam Status & Details
    udyam_status = determine_udyam_status(udyam)

    # 4. Domain Status & Details
    domain_provided = bool(job.get("claimed_domain") or domain.get("domain"))
    domain_status, ssl_status = determine_domain_status(domain, domain_provided=domain_provided)

    # 5. Name Matching
    best_match = matching.get("best_match") if isinstance(matching.get("best_match"), dict) else {}
    similarity_score = float(matching.get("score", 0.0))
    registered_name = best_match.get("name") or best_match.get("company_name") or mca.get("company_name") or gst.get("legal_name") or gst.get("trade_name")

    # 6. Address Consistency
    address_match = check_address_consistency(mca, gst, job)

    # 7. Calculate Identity Confidence
    identity_confidence = calculate_identity_confidence(
        mca_status=mca_status,
        gst_status=gst_status,
        udyam_status=udyam_status,
        domain_status=domain_status,
        similarity_score=similarity_score,
        address_match=address_match,
    )

    return {
        "company_name": company_name or "Not detected",
        "mca": {
            "status": mca_status,
            "incorporation_date": incorp_date,
            "registered_name": mca.get("company_name"),
            "registered_address": mca.get("registered_address") or mca.get("address"),
            "cin": mca.get("cin"),
        },
        "gst": {
            "status": gst_status,
            "gstin": job.get("gstin") or gst.get("gstin"),
            "registered_name": gst.get("legal_name") or gst.get("trade_name"),
            "business_address": gst.get("principal_address") or gst.get("address"),
        },
        "udyam": {
            "status": udyam_status,
            "registration_number": udyam.get("udyam_number"),
            "registered_name": udyam.get("enterprise_name"),
        },
        "domain": {
            "domain": domain.get("domain") or job.get("claimed_domain"),
            "status": domain_status,
            "domain_age_days": domain.get("domain_age_days"),
            "ssl_status": ssl_status,
            "registrant_org": domain.get("registrant_org"),
        },
        "name_match": {
            "claimed_name": matching.get("claimed_name") or company_name,
            "registered_name": registered_name,
            "similarity_score": round(similarity_score, 1),
            "no_match": matching.get("no_match", True),
        },
        "company_age_years": company_age,
        "identity_confidence": identity_confidence,
    }
