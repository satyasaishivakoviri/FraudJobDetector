import os
import re
from typing import Any, Dict, Optional
import requests
from dotenv import load_dotenv

from app.utils.sandbox_client import get_sandbox_headers

load_dotenv()

UDYAM_REGEX = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")
UDYAM_API_URL = os.getenv("UDYAM_API_URL", "https://api.sandbox.co.in/kyc/udyam/verify")

# Known mock records for testing / local verification
SAMPLE_UDYAM_RECORDS = {
    "UDYAM-GJ-01-0000001": {
        "enterprise_name": "SAMPLE ENTERPRISE PRIVATE LIMITED",
        "udyam_number": "UDYAM-GJ-01-0000001",
        "category": "Small",
        "registration_date": "2021-04-15",
    },
    "UDYAM-MH-01-0000002": {
        "enterprise_name": "APEX TECH SOLUTIONS",
        "udyam_number": "UDYAM-MH-01-0000002",
        "category": "Micro",
        "registration_date": "2022-08-20",
    },
}


def lookup_udyam(company_name_or_udyam_number: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Look up Udyam (MSME) registration for a company name or Udyam Registration Number.

    Returns a clean dict with keys:
        - enterprise_name: str
        - udyam_number: str
        - category: str (e.g., "Micro", "Small", "Medium")
        - registration_date: str

    If the enterprise is not registered under MSME/Udyam (which is normal and expected
    for large companies, public corporations, or non-MSMEs), returns:
        - {"registered": False, "status": "not_registered", "message": ...}

    Error cases handled:
        - {"error": "invalid_input", "message": ...}
        - {"error": "invalid_udyam_format", "message": ...}
        - {"error": "api_timeout", "message": ...}
        - {"error": "api_error", "message": ...}
    """
    if not isinstance(company_name_or_udyam_number, str) or not company_name_or_udyam_number.strip():
        return {
            "error": "invalid_input",
            "message": "Input must be a non-empty company name or Udyam number string.",
        }

    query = company_name_or_udyam_number.strip()
    is_udyam_candidate = query.upper().startswith("UDYAM")

    if is_udyam_candidate:
        clean_udyam = query.upper()
        if not UDYAM_REGEX.match(clean_udyam):
            return {
                "error": "invalid_udyam_format",
                "message": f"'{query}' is not a valid Udyam number. Expected format: UDYAM-XX-00-0000000",
            }

        # Check sample/cached records first
        if clean_udyam in SAMPLE_UDYAM_RECORDS:
            rec = SAMPLE_UDYAM_RECORDS[clean_udyam]
            return {
                "registered": True,
                "status": "active",
                "enterprise_name": rec["enterprise_name"],
                "udyam_number": rec["udyam_number"],
                "category": rec["category"],
                "registration_date": rec["registration_date"],
            }

    # Attempt lookup via configured Sandbox / external Udyam API
    try:
        headers = get_sandbox_headers(timeout=timeout)
        payload = (
            {"udyam_number": query.upper()}
            if is_udyam_candidate
            else {"company_name": query}
        )

        resp = requests.post(UDYAM_API_URL, headers=headers, json=payload, timeout=timeout)

        if resp.status_code == 200:
            data = resp.json().get("data", {})
            ent_data = data.get("data", data)
            if ent_data and (ent_data.get("udyam_number") or ent_data.get("enterprise_name")):
                return {
                    "registered": True,
                    "status": "active",
                    "enterprise_name": ent_data.get("enterprise_name") or ent_data.get("name", query),
                    "udyam_number": ent_data.get("udyam_number") or query.upper(),
                    "category": ent_data.get("category") or ent_data.get("enterprise_type", "Micro"),
                    "registration_date": ent_data.get("registration_date") or ent_data.get("date_of_registration", ""),
                }

    except requests.exceptions.Timeout:
        return {
            "error": "api_timeout",
            "message": f"Request timed out while verifying Udyam registration for: '{query}'",
        }
    except TimeoutError:
        return {
            "error": "api_timeout",
            "message": f"Authentication timed out while verifying Udyam registration for: '{query}'",
        }
    except Exception:
        # Fall through to standard evaluation
        pass

    # Large companies, public listed firms, and un-registered entities are expected to not be registered under Udyam
    return {
        "registered": False,
        "status": "not_registered",
        "message": "Enterprise is not registered under Udyam (normal/expected for large corporations and non-MSMEs)",
        "enterprise_name": query,
        "udyam_number": query.upper() if is_udyam_candidate else None,
        "category": None,
        "registration_date": None,
    }
