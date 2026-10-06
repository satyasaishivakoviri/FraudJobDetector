import re
from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz


def evaluate_offer_consistency(
    offer_data: Dict[str, Any],
    mca_result: Optional[Dict[str, Any]] = None,
    gst_result: Optional[Dict[str, Any]] = None,
    domain_result: Optional[Dict[str, Any]] = None,
    matching_result: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Evaluates consistency between claims made in an offer letter and verified statutory registry records.
    Returns a list of structured consistency item dictionaries:
    [
        {
            "field": "Company Name",
            "status": "✓ Match" | "⚠ Mismatch" | "? Not Verified" | "— Not Detected",
            "status_type": "match" | "mismatch" | "unverified" | "not_detected",
            "offer_value": str,
            "registry_value": Optional[str],
            "details": str
        },
        ...
    ]
    Strictly avoids false mismatches when statutory registry data is simply unavailable.
    """
    consistency_items: List[Dict[str, Any]] = []

    mca = mca_result or {}
    gst = gst_result or {}
    domain = domain_result or {}
    matching = matching_result or {}

    # -------------------------------------------------------------
    # 1. Company Name Consistency
    # -------------------------------------------------------------
    claimed_company = (offer_data.get("company_name") or "").strip()
    registry_company = (
        (matching.get("best_match") or {}).get("name")
        or mca.get("company_name")
        or gst.get("legal_name")
        or gst.get("trade_name")
    )

    if not claimed_company or claimed_company.lower() in {"not detected", "none"}:
        consistency_items.append(
            {
                "field": "Company Name",
                "status": "— Not Detected",
                "status_type": "not_detected",
                "offer_value": "Not detected",
                "registry_value": registry_company or "Not available",
                "details": "Company name was not identified in the offer letter.",
            }
        )
    elif registry_company:
        score = fuzz.token_set_ratio(claimed_company.lower(), registry_company.lower())
        if score >= 75:
            consistency_items.append(
                {
                    "field": "Company Name",
                    "status": "✓ Match",
                    "status_type": "match",
                    "offer_value": claimed_company,
                    "registry_value": registry_company,
                    "details": f"Offer letter entity aligns with statutory registry ({score}% match).",
                }
            )
        else:
            consistency_items.append(
                {
                    "field": "Company Name",
                    "status": "⚠ Mismatch",
                    "status_type": "mismatch",
                    "offer_value": claimed_company,
                    "registry_value": registry_company,
                    "details": f"Discrepancy: Offer claims '{claimed_company}', but registered entity is '{registry_company}'.",
                }
            )
    else:
        consistency_items.append(
            {
                "field": "Company Name",
                "status": "? Not Verified",
                "status_type": "unverified",
                "offer_value": claimed_company,
                "registry_value": "No registry record found",
                "details": "No matching statutory registry record was corroborated.",
            }
        )

    # -------------------------------------------------------------
    # 2. Company Address Consistency
    # -------------------------------------------------------------
    claimed_address = (offer_data.get("company_address") or offer_data.get("work_location") or "").strip()
    registry_address = (
        mca.get("registered_address")
        or mca.get("address")
        or gst.get("principal_place_of_business")
        or gst.get("registered_address")
    )

    if not claimed_address or claimed_address.lower() in {"not detected", "none"}:
        consistency_items.append(
            {
                "field": "Company Address",
                "status": "— Not Detected",
                "status_type": "not_detected",
                "offer_value": "Not detected",
                "registry_value": registry_address or "Not available",
                "details": "No registered address or location identified in the offer document.",
            }
        )
    elif registry_address:
        # Check common state/city keywords
        indian_states_and_cities = [
            "mumbai", "delhi", "bengaluru", "bangalore", "hyderabad", "pune", "chennai",
            "kolkata", "ahmedabad", "noida", "gurgaon", "gurugram", "jaipur", "chandigarh",
            "maharashtra", "karnataka", "telangana", "tamil nadu", "uttar pradesh", "haryana",
            "gujarat", "west bengal", "rajasthan", "kerala", "andhra pradesh"
        ]
        claimed_lower = claimed_address.lower()
        registry_lower = registry_address.lower()

        matched_geo = False
        conflicting_geo = False

        claimed_geos = [g for g in indian_states_and_cities if g in claimed_lower]
        registry_geos = [g for g in indian_states_and_cities if g in registry_lower]

        if claimed_geos and registry_geos:
            common = set(claimed_geos).intersection(set(registry_geos))
            if common:
                matched_geo = True
            else:
                conflicting_geo = True

        if matched_geo or fuzz.partial_ratio(claimed_lower, registry_lower) >= 65:
            consistency_items.append(
                {
                    "field": "Company Address",
                    "status": "✓ Match",
                    "status_type": "match",
                    "offer_value": claimed_address,
                    "registry_value": registry_address,
                    "details": "Address / jurisdiction corroborates with registered office.",
                }
            )
        elif conflicting_geo:
            consistency_items.append(
                {
                    "field": "Company Address",
                    "status": "⚠ Mismatch",
                    "status_type": "mismatch",
                    "offer_value": claimed_address,
                    "registry_value": registry_address,
                    "details": f"Jurisdiction mismatch: Offer states '{claimed_address}' while registry records '{registry_address}'.",
                }
            )
        else:
            consistency_items.append(
                {
                    "field": "Company Address",
                    "status": "? Not Verified",
                    "status_type": "unverified",
                    "offer_value": claimed_address,
                    "registry_value": registry_address,
                    "details": "Address could not be definitively matched against registry records.",
                }
            )
    else:
        consistency_items.append(
            {
                "field": "Company Address",
                "status": "? Not Verified",
                "status_type": "unverified",
                "offer_value": claimed_address,
                "registry_value": "No registry address available",
                "details": "Registry did not provide an official registered address for comparison.",
            }
        )

    # -------------------------------------------------------------
    # 3. Recruiter Email Domain Consistency
    # -------------------------------------------------------------
    recruiter_email = (offer_data.get("recruiter_email") or "").strip()
    official_domain = (offer_data.get("company_domain") or domain.get("domain") or "").strip().lower()

    if not recruiter_email or recruiter_email.lower() in {"not detected", "none"}:
        consistency_items.append(
            {
                "field": "Email Domain",
                "status": "— Not Detected",
                "status_type": "not_detected",
                "offer_value": "Not detected",
                "registry_value": official_domain or "Not available",
                "details": "No recruiter contact email found in offer letter.",
            }
        )
    else:
        email_parts = recruiter_email.split("@")
        email_domain = email_parts[1].lower() if len(email_parts) == 2 else ""
        free_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "rediffmail.com", "protonmail.com"}

        if official_domain:
            norm_official = official_domain.replace("https://", "").replace("http://", "").split("/")[0].lstrip("www.")
            if email_domain == norm_official or email_domain.endswith("." + norm_official):
                consistency_items.append(
                    {
                        "field": "Email Domain",
                        "status": "✓ Match",
                        "status_type": "match",
                        "offer_value": recruiter_email,
                        "registry_value": f"@{norm_official}",
                        "details": f"Email domain aligns with official company domain (@{norm_official}).",
                    }
                )
            elif email_domain in free_domains:
                consistency_items.append(
                    {
                        "field": "Email Domain",
                        "status": "⚠ Mismatch",
                        "status_type": "mismatch",
                        "offer_value": recruiter_email,
                        "registry_value": f"@{norm_official}",
                        "details": f"Recruiter uses free/personal email (@{email_domain}) instead of corporate domain (@{norm_official}).",
                    }
                )
            else:
                consistency_items.append(
                    {
                        "field": "Email Domain",
                        "status": "⚠ Mismatch",
                        "status_type": "mismatch",
                        "offer_value": recruiter_email,
                        "registry_value": f"@{norm_official}",
                        "details": f"Email domain (@{email_domain}) does not match corporate domain (@{norm_official}).",
                    }
                )
        elif email_domain in free_domains:
            consistency_items.append(
                {
                    "field": "Email Domain",
                    "status": "⚠ Mismatch",
                    "status_type": "mismatch",
                    "offer_value": recruiter_email,
                    "registry_value": "Corporate Domain Expected",
                    "details": f"Recruiter contact is on a personal/free email provider (@{email_domain}).",
                }
            )
        else:
            consistency_items.append(
                {
                    "field": "Email Domain",
                    "status": "? Not Verified",
                    "status_type": "unverified",
                    "offer_value": recruiter_email,
                    "registry_value": "No official domain verified",
                    "details": "Cannot verify email authenticity without verified company domain.",
                }
            )

    # -------------------------------------------------------------
    # 4. CIN Consistency
    # -------------------------------------------------------------
    claimed_cin = (offer_data.get("cin") or "").strip().upper()
    registry_cin = (mca.get("cin") or "").strip().upper()

    if not claimed_cin or claimed_cin in {"NOT DETECTED", "NONE"}:
        consistency_items.append(
            {
                "field": "CIN",
                "status": "— Not Detected",
                "status_type": "not_detected",
                "offer_value": "Not detected",
                "registry_value": registry_cin or "Not available",
                "details": "Corporate Identification Number (CIN) was not cited in the offer.",
            }
        )
    elif registry_cin:
        if claimed_cin == registry_cin:
            consistency_items.append(
                {
                    "field": "CIN",
                    "status": "✓ Match",
                    "status_type": "match",
                    "offer_value": claimed_cin,
                    "registry_value": registry_cin,
                    "details": f"CIN matches verified Ministry of Corporate Affairs record ({claimed_cin}).",
                }
            )
        else:
            consistency_items.append(
                {
                    "field": "CIN",
                    "status": "⚠ Mismatch",
                    "status_type": "mismatch",
                    "offer_value": claimed_cin,
                    "registry_value": registry_cin,
                    "details": f"Claimed CIN '{claimed_cin}' differs from registered MCA record '{registry_cin}'.",
                }
            )
    else:
        consistency_items.append(
            {
                "field": "CIN",
                "status": "? Not Verified",
                "status_type": "unverified",
                "offer_value": claimed_cin,
                "registry_value": "Not found in MCA",
                "details": f"Claimed CIN '{claimed_cin}' could not be validated against MCA database.",
            }
        )

    # -------------------------------------------------------------
    # 5. GSTIN Consistency
    # -------------------------------------------------------------
    claimed_gstin = (offer_data.get("gstin") or "").strip().upper()
    registry_gstin = (gst.get("gstin") or "").strip().upper()
    gst_status = (gst.get("status") or "").strip().lower()

    if not claimed_gstin or claimed_gstin in {"NOT DETECTED", "NONE"}:
        consistency_items.append(
            {
                "field": "GSTIN",
                "status": "— Not Detected",
                "status_type": "not_detected",
                "offer_value": "Not detected",
                "registry_value": registry_gstin or "Not available",
                "details": "GST identification number was not cited in the offer.",
            }
        )
    elif registry_gstin:
        if claimed_gstin == registry_gstin and gst_status in {"active", "verified"}:
            consistency_items.append(
                {
                    "field": "GSTIN",
                    "status": "✓ Match",
                    "status_type": "match",
                    "offer_value": claimed_gstin,
                    "registry_value": f"{registry_gstin} ({gst_status.title()})",
                    "details": "GSTIN matches an active taxpayer registration.",
                }
            )
        elif claimed_gstin == registry_gstin and gst_status in {"cancelled", "suspended", "inactive"}:
            consistency_items.append(
                {
                    "field": "GSTIN",
                    "status": "⚠ Mismatch",
                    "status_type": "mismatch",
                    "offer_value": claimed_gstin,
                    "registry_value": f"{registry_gstin} ({gst_status.title()})",
                    "details": f"GSTIN matches record, but registration is {gst_status.upper()}.",
                }
            )
        else:
            consistency_items.append(
                {
                    "field": "GSTIN",
                    "status": "⚠ Mismatch",
                    "status_type": "mismatch",
                    "offer_value": claimed_gstin,
                    "registry_value": registry_gstin,
                    "details": f"Claimed GSTIN '{claimed_gstin}' differs from GST record '{registry_gstin}'.",
                }
            )
    else:
        consistency_items.append(
            {
                "field": "GSTIN",
                "status": "? Not Verified",
                "status_type": "unverified",
                "offer_value": claimed_gstin,
                "registry_value": "Not verified",
                "details": f"GSTIN '{claimed_gstin}' could not be corroborated on the GST portal.",
            }
        )

    # -------------------------------------------------------------
    # 6. Salary / Stipend Extraction Indicator
    # -------------------------------------------------------------
    salary = offer_data.get("salary") or offer_data.get("stipend")
    if salary and str(salary).strip().lower() not in {"not detected", "none"}:
        consistency_items.append(
            {
                "field": "Salary",
                "status": "✓ Extracted",
                "status_type": "match",
                "offer_value": str(salary).strip(),
                "registry_value": "Internal compensation term",
                "details": f"Compensation stated in offer: {salary}",
            }
        )
    else:
        consistency_items.append(
            {
                "field": "Salary",
                "status": "— Not Detected",
                "status_type": "not_detected",
                "offer_value": "Not detected",
                "registry_value": "—",
                "details": "No explicit salary or stipend amount identified.",
            }
        )

    # -------------------------------------------------------------
    # 7. Joining Date Extraction Indicator
    # -------------------------------------------------------------
    joining_date = offer_data.get("joining_date")
    if joining_date and str(joining_date).strip().lower() not in {"not detected", "none"}:
        consistency_items.append(
            {
                "field": "Joining Date",
                "status": "✓ Extracted",
                "status_type": "match",
                "offer_value": str(joining_date).strip(),
                "registry_value": "Internal onboarding schedule",
                "details": f"Date of joining specified in offer: {joining_date}",
            }
        )
    else:
        consistency_items.append(
            {
                "field": "Joining Date",
                "status": "— Not Detected",
                "status_type": "not_detected",
                "offer_value": "Not detected",
                "registry_value": "—",
                "details": "No specific joining date identified.",
            }
        )

    return consistency_items
