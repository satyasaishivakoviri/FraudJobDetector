import datetime
import secrets
from typing import Any, Dict, List, Optional

from app.utils.identity import build_company_identity
from app.utils.matching import match_company_name
from app.utils.offer_consistency import evaluate_offer_consistency
from app.utils.safety_recommendations import generate_safety_recommendations
from app.utils.scoring import evaluate_rules
from app.verifiers.domain import check_domain
from app.verifiers.gst import lookup_gst
from app.verifiers.mca import lookup_mca
from app.verifiers.udyam import lookup_udyam


def verify_company(
    company_name: str,
    claimed_domain: Optional[str] = None,
    gstin: Optional[str] = None,
    contact_email: Optional[str] = None,
    job_message: Optional[str] = None,
    description: Optional[str] = None,
    notes: Optional[str] = None,
    offer_data: Optional[Dict[str, Any]] = None,
    previous_result: Optional[Dict[str, Any]] = None,
    input_source: Optional[str] = "message",
    verification_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified verification engine used by both POST /check-company and POST /recheck-company.
    Performs statutory registry queries (MCA, GST, Udyam), domain evaluation, fuzzy name
    matching, risk rule evaluation, offer consistency evaluation, and safety recommendations.
    Attaches server timestamp 'verified_at' and detects verification differences against
    'previous_result' when provided.
    """
    clean_company_name = (company_name or "").strip()
    if not clean_company_name:
        raise ValueError("company_name cannot be blank.")

    # 1. MCA Company Lookup
    try:
        mca_result = lookup_mca(clean_company_name)
    except Exception as e:
        mca_result = {"error": "api_error", "message": str(e)}

    # 2. GST Lookup (when gstin is provided)
    gst_result: Dict[str, Any] = {}
    clean_gstin = (gstin or "").strip().upper()
    if clean_gstin:
        try:
            gst_result = lookup_gst(clean_gstin)
        except Exception as e:
            gst_result = {"error": "api_error", "message": str(e)}

    # 3. Udyam Lookup
    try:
        udyam_result = lookup_udyam(clean_company_name)
    except Exception as e:
        udyam_result = {"error": "api_error", "message": str(e)}

    # 4. Domain/WHOIS & SSL Check (when claimed_domain is provided)
    domain_result: Dict[str, Any] = {}
    clean_domain = (claimed_domain or "").strip()
    if clean_domain:
        try:
            domain_result = check_domain(clean_domain)
        except Exception as e:
            domain_result = {"error": "api_error", "message": str(e), "ssl_status": "unavailable"}

    # 5. Aggregate registry candidates for fuzzy company name matching
    registry_candidates: List[Dict[str, Any]] = []

    if mca_result.get("company_name"):
        registry_candidates.append(
            {
                "name": mca_result["company_name"],
                "source": "mca",
                "cin": mca_result.get("cin"),
            }
        )

    if gst_result.get("legal_name"):
        registry_candidates.append(
            {
                "name": gst_result["legal_name"],
                "source": "gst_legal",
                "gstin": clean_gstin,
            }
        )
    if gst_result.get("trade_name") and gst_result["trade_name"] != gst_result.get("legal_name"):
        registry_candidates.append(
            {
                "name": gst_result["trade_name"],
                "source": "gst_trade",
                "gstin": clean_gstin,
            }
        )

    if udyam_result.get("registered") and udyam_result.get("enterprise_name"):
        registry_candidates.append(
            {
                "name": udyam_result["enterprise_name"],
                "source": "udyam",
                "udyam_number": udyam_result.get("udyam_number"),
            }
        )

    # 6. Fuzzy Entity Matching
    try:
        matching_result = match_company_name(
            claimed_name=clean_company_name,
            registry_results=registry_candidates,
        )
    except Exception:
        matching_result = {
            "claimed_name": clean_company_name,
            "best_match": None,
            "score": 0.0,
            "no_match": True,
        }

    # 7. Evaluate Rule Engine
    message_content = job_message or description or ""
    # If offer letter fee was extracted, append to notes to guarantee rule trigger
    extra_notes = notes or ""
    if offer_data and offer_data.get("payment_or_fee"):
        extra_notes += f" [Offer fee detected: {offer_data['payment_or_fee']}]"

    job_details: Dict[str, Any] = {
        "company_name": clean_company_name,
        "claimed_domain": clean_domain,
        "gstin": clean_gstin,
        "contact_email": contact_email,
        "recruiter_email": contact_email,
        "job_message": message_content,
        "description": message_content,
        "notes": extra_notes,
    }

    scoring_result = evaluate_rules(
        gst_result=gst_result,
        mca_result=mca_result,
        udyam_result=udyam_result,
        domain_result=domain_result,
        matching_result=matching_result,
        job_details=job_details,
    )

    risk_score = scoring_result.get("risk_score", 0)
    risk_level = scoring_result.get("risk_level", "LOW")
    reasons = scoring_result.get("reasons", [])

    # 8. Attach Official Source Metadata
    mca_source = {
        "name": "Ministry of Corporate Affairs",
        "url": "https://www.mca.gov.in/content/mca/global/en/mca/fo-library/company-master-data.html",
    }
    gst_source = {
        "name": "GST Taxpayer Verification",
        "url": "https://services.gst.gov.in/services/searchtp" if (clean_gstin or (gst_result and gst_result.get("gstin"))) else None,
    }
    udyam_source = {
        "name": "Udyam Registration Portal",
        "url": "https://udyamregistration.gov.in/Udyam_Verify.aspx" if (udyam_result and udyam_result.get("registered")) else None,
    }
    domain_source = {
        "name": "Domain / WHOIS Verification",
        "url": None,
    }
    matching_source = {
        "name": "MCA Company Registry",
        "url": "https://www.mca.gov.in/content/mca/global/en/mca/fo-library/company-master-data.html",
    }

    if isinstance(mca_result, dict):
        mca_result["source"] = mca_source
    if isinstance(gst_result, dict):
        gst_result["source"] = gst_source
    if isinstance(udyam_result, dict):
        udyam_result["source"] = udyam_source
    if isinstance(domain_result, dict):
        domain_result["source"] = domain_source
    if isinstance(matching_result, dict):
        matching_result["source"] = matching_source

    company_identity = build_company_identity(
        company_name=clean_company_name,
        mca_result=mca_result,
        gst_result=gst_result,
        udyam_result=udyam_result,
        domain_result=domain_result,
        matching_result=matching_result,
        job_details=job_details,
    )

    # 9. Offer Letter Consistency
    offer_consistency_items: List[Dict[str, Any]] = []
    if offer_data:
        offer_consistency_items = evaluate_offer_consistency(
            offer_data=offer_data,
            mca_result=mca_result,
            gst_result=gst_result,
            domain_result=domain_result,
            matching_result=matching_result,
        )

    # 10. Server Timestamp
    now = datetime.datetime.now()
    verified_at = now.strftime("%d %B %Y, %I:%M %p")
    verified_at_iso = now.isoformat()

    # 11. Compare against previous verification result if provided
    verification_changes: List[Dict[str, Any]] = []
    has_changes = False

    if previous_result and isinstance(previous_result, dict):
        prev_mca = previous_result.get("mca") if "mca" in previous_result else previous_result.get("mca_result", {})
        prev_mca = prev_mca or {}
        # Compare MCA Status
        prev_mca_status = prev_mca.get("status") or "Not Available"
        curr_mca_status = mca_result.get("status") or "Not Available"
        if str(prev_mca_status).strip().lower() != str(curr_mca_status).strip().lower():
            has_changes = True
            verification_changes.append(
                {
                    "field": "MCA Status",
                    "previous": str(prev_mca_status).title(),
                    "current": str(curr_mca_status).title(),
                    "changed": True,
                    "message": f"MCA status changed from {prev_mca_status} to {curr_mca_status}.",
                }
            )

        # Compare MCA Company Name
        prev_mca_name = prev_mca.get("company_name")
        curr_mca_name = mca_result.get("company_name")
        if prev_mca_name and curr_mca_name and prev_mca_name.strip().lower() != curr_mca_name.strip().lower():
            has_changes = True
            verification_changes.append(
                {
                    "field": "Registered Company Name",
                    "previous": prev_mca_name,
                    "current": curr_mca_name,
                    "changed": True,
                    "message": f"Registered entity name updated to '{curr_mca_name}'.",
                }
            )

        # Compare GST Status
        prev_gst = previous_result.get("gst") if "gst" in previous_result else previous_result.get("gst_result", {})
        prev_gst = prev_gst or {}
        prev_gst_status = prev_gst.get("status")
        curr_gst_status = gst_result.get("status")
        if prev_gst_status and curr_gst_status and str(prev_gst_status).strip().lower() != str(curr_gst_status).strip().lower():
            has_changes = True
            verification_changes.append(
                {
                    "field": "GST Status",
                    "previous": str(prev_gst_status).title(),
                    "current": str(curr_gst_status).title(),
                    "changed": True,
                    "message": f"GST taxpayer status changed from {prev_gst_status} to {curr_gst_status}.",
                }
            )

        # Compare Domain SSL Status
        prev_domain = previous_result.get("domain") if "domain" in previous_result else previous_result.get("domain_result", {})
        prev_domain = prev_domain or {}
        prev_ssl = prev_domain.get("ssl_status")
        curr_ssl = domain_result.get("ssl_status")
        if prev_ssl and curr_ssl and str(prev_ssl).strip().lower() != str(curr_ssl).strip().lower():
            has_changes = True
            verification_changes.append(
                {
                    "field": "SSL Certificate Status",
                    "previous": str(prev_ssl).title(),
                    "current": str(curr_ssl).title(),
                    "changed": True,
                    "message": f"Domain SSL status updated from {prev_ssl} to {curr_ssl}.",
                }
            )

        # Compare Risk Score
        prev_score = previous_result.get("risk_score")
        if prev_score is not None and int(prev_score) != int(risk_score):
            has_changes = True
            verification_changes.append(
                {
                    "field": "Risk Score",
                    "previous": str(prev_score),
                    "current": str(risk_score),
                    "changed": True,
                    "message": f"Risk score recalculated from {prev_score} to {risk_score}.",
                }
            )

        # Compare Risk Level
        prev_level = previous_result.get("risk_level")
        if prev_level and str(prev_level).upper() != str(risk_level).upper():
            has_changes = True
            verification_changes.append(
                {
                    "field": "Risk Level",
                    "previous": str(prev_level).upper(),
                    "current": str(risk_level).upper(),
                    "changed": True,
                    "message": f"Overall risk classification changed from {prev_level} to {risk_level}.",
                }
            )

    # Ensure stable verification_id (preserves existing on recheck)
    if not verification_id:
        if previous_result and isinstance(previous_result, dict) and previous_result.get("verification_id"):
            verification_id = previous_result.get("verification_id")
        else:
            verification_id = f"VER-{now.year}-{secrets.randbelow(90000) + 10000}"

    base_result = {
        "verification_id": verification_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reasons": reasons,
        "triggered_rules": scoring_result.get("triggered_rules", []),
        "mca_result": mca_result,
        "gst_result": gst_result,
        "udyam_result": udyam_result,
        "domain_result": domain_result,
        "matching_result": matching_result,
        "company_match": matching_result,
        "company_identity": company_identity,
        "mca": mca_result,
        "gst": gst_result,
        "udyam": udyam_result,
        "domain": domain_result,
        "offer_letter_consistency": offer_consistency_items,
        "offer_data": offer_data,
        "job_details": {
            "job_message": job_message,
            "description": description,
            "notes": notes,
        },
        "input_source": input_source,
        "verified_at": verified_at,
        "verified_at_iso": verified_at_iso,
        "verification_changes": verification_changes,
        "has_changes": has_changes,
    }

    # Generate structured dynamic safety recommendations
    dynamic_recommendations = generate_safety_recommendations(base_result)
    base_result["safety_recommendations"] = dynamic_recommendations

    return base_result
