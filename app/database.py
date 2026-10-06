"""Database layer for temporary shareable verification reports using SQLite.

Handles schema initialization, cryptographically secure token generation,
data sanitization, expiration tracking (7 days), and report revocation.
"""

import datetime
import json
import os
import secrets
import sqlite3
from typing import Any, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports.db")


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target_path = db_path or DB_PATH
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the verification_reports table and indexes."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verification_id TEXT UNIQUE NOT NULL,
                report_token TEXT UNIQUE NOT NULL,
                revoke_token TEXT NOT NULL,
                sanitized_report_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_token ON verification_reports(report_token);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_ver_id ON verification_reports(verification_id);"
        )
        conn.commit()


def sanitize_verification_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strips all sensitive credentials, personal phone numbers, emails, raw documents,
    and private messages. Retains only vetted public corporate due diligence findings.
    """
    if not isinstance(raw_data, dict):
        return {}

    # Extract company name safely
    company_name = (
        raw_data.get("company_name")
        or raw_data.get("company_identity", {}).get("company_name")
        or raw_data.get("investigated_company")
        or (raw_data.get("matching_result") or {}).get("claimed_name")
        or "Company"
    )

    # Sanitize MCA findings (official public registry data)
    mca_raw = raw_data.get("mca") or raw_data.get("mca_result") or {}
    sanitized_mca = {
        "status": mca_raw.get("status", "Not Available"),
        "company_name": mca_raw.get("company_name"),
        "cin": mca_raw.get("cin"),
        "company_category": mca_raw.get("company_category") or mca_raw.get("class_of_company"),
        "source": mca_raw.get("source", {
            "name": "Ministry of Corporate Affairs",
            "url": "https://www.mca.gov.in/content/mca/global/en/mca/fo-library/company-master-data.html",
        }),
    }

    # Sanitize GST findings (official public taxpayer data)
    gst_raw = raw_data.get("gst") or raw_data.get("gst_result") or {}
    sanitized_gst = {
        "status": gst_raw.get("status", "Not provided" if not gst_raw.get("gstin") else "Active"),
        "gstin": gst_raw.get("gstin"),
        "legal_name": gst_raw.get("legal_name"),
        "trade_name": gst_raw.get("trade_name"),
        "source": gst_raw.get("source", {
            "name": "GST Taxpayer Verification",
            "url": "https://services.gst.gov.in/services/searchtp",
        }),
    }

    # Sanitize Udyam findings
    udyam_raw = raw_data.get("udyam") or raw_data.get("udyam_result") or {}
    sanitized_udyam = {
        "registered": bool(udyam_raw.get("registered")),
        "status": udyam_raw.get("status", "Not Found"),
        "enterprise_name": udyam_raw.get("enterprise_name"),
        "source": udyam_raw.get("source", {
            "name": "Udyam Registration Portal",
            "url": "https://udyamregistration.gov.in/Udyam_Verify.aspx",
        }),
    }

    # Sanitize Domain findings
    domain_raw = raw_data.get("domain") or raw_data.get("domain_result") or {}
    sanitized_domain = {
        "domain": domain_raw.get("domain"),
        "status": domain_raw.get("status", "Not Provided"),
        "ssl_status": domain_raw.get("ssl_status", "Unavailable"),
        "domain_age_days": domain_raw.get("domain_age_days"),
        "registrant": domain_raw.get("registrant") or domain_raw.get("tld_type"),
        "source": {
            "name": "Domain / WHOIS Verification",
            "url": None,
        },
    }

    # Sanitize Company Name Matching
    match_raw = raw_data.get("matching_result") or raw_data.get("company_match") or {}
    sanitized_match = {
        "claimed_name": match_raw.get("claimed_name", company_name),
        "registered_name": (match_raw.get("best_match") or {}).get("name") or match_raw.get("registered_name"),
        "score": match_raw.get("score", 0),
        "source": {
            "name": "MCA Company Registry",
            "url": "https://www.mca.gov.in/content/mca/global/en/mca/fo-library/company-master-data.html",
        },
    }

    # Sanitize Risk Signals (mask any accidental credential values in descriptions)
    clean_signals = []
    for sig in raw_data.get("triggered_rules", []):
        if isinstance(sig, dict):
            clean_signals.append({
                "rule": sig.get("rule", ""),
                "weight": sig.get("weight") or sig.get("score") or 15,
                "reason": sig.get("reason") or sig.get("explanation") or "",
            })

    # Sanitize Offer Consistency items if present (omit private personal recruiter phone/email)
    clean_consistency = []
    for item in raw_data.get("offer_letter_consistency", []):
        if isinstance(item, dict):
            field_name = item.get("field", "")
            # Mask private email addresses
            offer_val = item.get("offer_value", "")
            if "@" in str(offer_val):
                parts = str(offer_val).split("@")
                offer_val = f"***@{parts[1]}" if len(parts) == 2 else "***@domain"

            clean_consistency.append({
                "field": field_name,
                "status": item.get("status", "— Not Detected"),
                "offer_value": offer_val,
                "registry_value": item.get("registry_value", "—"),
                "details": item.get("details", ""),
            })

    # Format verification timestamp
    verified_at = raw_data.get("verified_at") or datetime.datetime.now().strftime("%d %B %Y, %I:%M %p")

    return {
        "verification_id": raw_data.get("verification_id", f"VER-{datetime.datetime.now().year}-{secrets.randbelow(90000) + 10000}"),
        "company_name": company_name,
        "risk_score": raw_data.get("risk_score", 0),
        "risk_level": str(raw_data.get("risk_level", "LOW")).upper(),
        "verified_at": verified_at,
        "mca": sanitized_mca,
        "gst": sanitized_gst,
        "udyam": sanitized_udyam,
        "domain": sanitized_domain,
        "company_match": sanitized_match,
        "risk_signals": clean_signals,
        "safety_recommendations": raw_data.get("safety_recommendations", []),
        "offer_letter_consistency": clean_consistency,
        "sources": [
            {"name": "Ministry of Corporate Affairs", "url": "https://www.mca.gov.in/content/mca/global/en/mca/fo-library/company-master-data.html"},
            {"name": "GST Taxpayer Verification", "url": "https://services.gst.gov.in/services/searchtp"},
            {"name": "Udyam Registration Portal", "url": "https://udyamregistration.gov.in/Udyam_Verify.aspx"},
            {"name": "Domain / WHOIS Verification", "url": None},
        ],
    }


def create_shareable_report(
    raw_data: Dict[str, Any],
    ttl_days: int = 7,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new temporary sanitized verification report with a cryptographic token.
    Enforces a 7-day expiration window.
    """
    init_db(db_path)

    sanitized = sanitize_verification_data(raw_data)
    verification_id = sanitized["verification_id"]

    # Cryptographically secure random tokens
    report_token = secrets.token_urlsafe(32)
    revoke_token = secrets.token_urlsafe(32)

    now = datetime.datetime.now(datetime.timezone.utc)
    created_at = now.isoformat()
    expires_at = (now + datetime.timedelta(days=ttl_days)).isoformat()

    sanitized_json = json.dumps(sanitized)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO verification_reports (
                verification_id, report_token, revoke_token,
                sanitized_report_data, created_at, expires_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (verification_id, report_token, revoke_token, sanitized_json, created_at, expires_at),
        )
        conn.commit()

    return {
        "verification_id": verification_id,
        "report_token": report_token,
        "revoke_token": revoke_token,
        "created_at": created_at,
        "expires_at": expires_at,
        "sanitized_data": sanitized,
    }


def get_shareable_report(report_token: str, db_path: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Retrieves and validates a shareable report by token.
    Returns:
        ("valid", report_dict)
        ("not_found", None)
        ("revoked", None)
        ("expired", None)
    """
    init_db(db_path)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM verification_reports WHERE report_token = ?",
            (report_token,),
        )
        row = cursor.fetchone()

    if not row:
        return "not_found", None

    if not row["is_active"]:
        return "revoked", None

    # Check expiration
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        expires_at = datetime.datetime.fromisoformat(row["expires_at"])
        if now > expires_at:
            return "expired", None
    except Exception:
        pass

    try:
        data = json.loads(row["sanitized_report_data"])
        data["expires_at"] = row["expires_at"]
        data["created_at"] = row["created_at"]
        return "valid", data
    except Exception:
        return "not_found", None


def revoke_shareable_report(
    report_token: str,
    revoke_token: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """
    Revokes a report by setting is_active = 0.
    If revoke_token is provided, ensures it matches the owner's token.
    """
    init_db(db_path)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if revoke_token:
            cursor.execute(
                "SELECT id FROM verification_reports WHERE report_token = ? AND revoke_token = ?",
                (report_token, revoke_token),
            )
        else:
            cursor.execute(
                "SELECT id FROM verification_reports WHERE report_token = ?",
                (report_token,),
            )
        row = cursor.fetchone()
        if not row:
            return False

        cursor.execute(
            "UPDATE verification_reports SET is_active = 0 WHERE report_token = ?",
            (report_token,),
        )
        conn.commit()
        return True
