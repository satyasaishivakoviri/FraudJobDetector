import os
from typing import Any, Dict, List, Tuple
import requests
from dotenv import load_dotenv
from rapidfuzz import fuzz

from app.utils.sandbox_client import get_sandbox_headers

load_dotenv()

DATAGOV_API_KEY = os.getenv(
    "DATAGOV_API_KEY", "579b464db66ec23bdd00000135d0e2496e304a7e709d31f65feedc4c"
)
DATAGOV_MCA_URL = "https://api.data.gov.in/resource/4dbe5667-7b6b-41d7-82af-211562424d9a"

SANDBOX_MCA_SEARCH_URL = "https://api.sandbox.co.in/kyc/mca/company/master-data/search"
SANDBOX_MCA_MASTER_URL = "https://api.sandbox.co.in/kyc/mca/company/master-data"


def _search_mca_sandbox(company_name: str, timeout: int = 10) -> Tuple[str, Any]:
    """
    Search MCA records using Sandbox KYC API.

    Returns:
        ("ok", data_dict) on success
        ("not_found", msg) when company is explicitly not found
        ("timeout", msg) when upstream or request timed out
        ("error", msg) on other failures
    """
    headers = get_sandbox_headers(timeout=timeout)
    params = {"company_name": company_name}

    try:
        resp = requests.get(SANDBOX_MCA_SEARCH_URL, headers=headers, params=params, timeout=timeout)
    except requests.exceptions.Timeout:
        return ("timeout", "Request timed out while connecting to Sandbox MCA search.")
    except Exception as e:
        return ("error", str(e))

    # Parse JSON if available
    res_json = {}
    try:
        res_json = resp.json()
    except Exception:
        pass

    # Status 521 or explicit 'not found' message
    msg = str(res_json.get("message", "")).lower()
    if resp.status_code == 521 or "not found" in msg:
        return ("not_found", f"Company master data not found for: '{company_name}'")

    # Gateway timeout from Sandbox
    if resp.status_code == 504 or res_json.get("code") == 504 or "timed out" in msg:
        return ("timeout", "Sandbox upstream MCA service timed out.")

    if resp.status_code == 404:
        return ("not_found", f"No MCA record found for: '{company_name}'")

    if resp.status_code != 200:
        return ("error", f"Sandbox MCA search returned status {resp.status_code}: {msg}")

    data = res_json.get("data", {})
    records: List[Dict[str, Any]] = data.get("records", []) if isinstance(data, dict) else []
    if not records:
        return ("not_found", f"No records returned for '{company_name}'")

    # Pick the best matching record
    best_record = records[0]
    if len(records) > 1:
        best_score = -1.0
        normalized_query = company_name.strip().lower()
        for rec in records:
            cname = rec.get("company_name", "").strip().lower()
            score = fuzz.token_set_ratio(normalized_query, cname)
            if score > best_score:
                best_score = score
                best_record = rec

    cin = best_record.get("cin")
    if not cin:
        return ("not_found", "No CIN associated with matching record")

    # Fetch full master data for the CIN
    try:
        master_resp = requests.post(
            SANDBOX_MCA_MASTER_URL,
            headers=headers,
            json={"cin": cin},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return ("timeout", f"Request timed out while fetching master data for CIN: {cin}")
    except Exception as e:
        return ("error", str(e))

    if master_resp.status_code == 200:
        master_data = master_resp.json().get("data", {})
        return (
            "ok",
            {
                "company_name": master_data.get("company_name") or best_record.get("company_name", ""),
                "cin": master_data.get("cin") or cin,
                "status": master_data.get("company_status") or "Unknown",
                "incorporation_date": master_data.get("company_registration_date") or "",
                "registered_address": master_data.get("registered_office_address") or "",
                "directors": master_data.get("directors", []),
            },
        )

    # Fallback to basic record if master data detail endpoint fails
    return (
        "ok",
        {
            "company_name": best_record.get("company_name", ""),
            "cin": cin,
            "status": "Unknown",
            "incorporation_date": "",
            "registered_address": "",
            "directors": [],
        },
    )


def _search_mca_datagov(company_name: str, timeout: int = 5) -> Tuple[str, Any]:
    """
    Fallback search using data.gov.in Open Government Data API.
    """
    if not DATAGOV_API_KEY:
        return ("error", "No data.gov.in API key configured.")

    params = {
        "api-key": DATAGOV_API_KEY,
        "format": "json",
        "limit": 5,
        "filters[company_name]": company_name.strip(),
    }
    try:
        resp = requests.get(DATAGOV_MCA_URL, params=params, timeout=timeout)
    except requests.exceptions.Timeout:
        return ("timeout", "Timeout querying data.gov.in MCA dataset")
    except Exception as e:
        return ("error", str(e))

    if resp.status_code != 200:
        return ("error", f"data.gov.in returned status {resp.status_code}")

    res_json = resp.json()
    records = res_json.get("records", [])
    if not records:
        return ("not_found", f"No records found on data.gov.in for '{company_name}'")

    best = records[0]
    return (
        "ok",
        {
            "company_name": best.get("company_name", ""),
            "cin": best.get("cin", ""),
            "status": best.get("company_status", "Unknown"),
            "incorporation_date": best.get("date_of_registration") or best.get("company_registration_date", ""),
            "registered_address": best.get("registered_office_address", ""),
            "directors": best.get("directors", []),
        },
    )


def lookup_mca(company_name: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Search MCA/CIN data for a given company name.

    Returns a clean dict with keys:
        - company_name: str
        - cin: str
        - status: str
        - incorporation_date: str
        - registered_address: str
        - directors: list

    Handles invalid input, API timeouts, and 'no match found' separately without unhandled exceptions.
    """
    if not isinstance(company_name, str) or not company_name.strip():
        return {
            "error": "invalid_input",
            "message": "Company name must be a non-empty string.",
        }

    clean_name = company_name.strip()

    try:
        # Primary provider: Sandbox KYC MCA API
        status_type, result = _search_mca_sandbox(clean_name, timeout=timeout)

        if status_type == "ok":
            return result

        if status_type == "not_found":
            return {
                "error": "no_match_found",
                "message": f"No MCA company records found matching: '{clean_name}'",
            }

        if status_type == "timeout":
            return {
                "error": "api_timeout",
                "message": f"Request timed out while connecting to MCA verification API for: '{clean_name}'",
            }

        # If Sandbox returned an unexpected error, try data.gov.in fallback
        dg_status, dg_result = _search_mca_datagov(clean_name, timeout=min(timeout, 5))
        if dg_status == "ok":
            return dg_result

        if dg_status == "timeout":
            return {
                "error": "api_timeout",
                "message": f"Request timed out while connecting to MCA API for: '{clean_name}'",
            }

        if dg_status == "not_found":
            return {
                "error": "no_match_found",
                "message": f"No MCA company records found matching: '{clean_name}'",
            }

        return {
            "error": "api_error",
            "message": f"MCA lookup failed: {result}",
        }

    except requests.exceptions.Timeout:
        return {
            "error": "api_timeout",
            "message": f"Request timed out while connecting to MCA verification API for: '{clean_name}'",
        }
    except Exception as e:
        return {
            "error": "api_error",
            "message": f"Unhandled error during MCA lookup: {str(e)}",
        }
