import re
from typing import Any, Dict
import requests
from app.utils.sandbox_client import get_sandbox_headers

# Standard 15-character GSTIN pattern:
# 2 digits state code + 10 chars PAN + 1 entity code + 'Z' + 1 check character
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
GST_SEARCH_URL = "https://api.sandbox.co.in/gst/compliance/public/gstin/search"
GST_VERIFY_URL = "https://api.sandbox.co.in/gst/compliance/public/gstin/verify"


def lookup_gst(gstin: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Look up taxpayer details for a given GSTIN using Sandbox GST compliance API.

    Returns a clean dict with keys:
        - legal_name: str
        - trade_name: str
        - status: str
        - state: str
        - registration_date: str

    On error, returns:
        - {"error": "invalid_gstin_format", "message": ...}
        - {"error": "api_timeout", "message": ...}
        - {"error": "no_match_found", "message": ...}
        - {"error": "api_error", "message": ...}
    """
    if not isinstance(gstin, str):
        return {
            "error": "invalid_gstin_format",
            "message": "GSTIN must be a string.",
        }

    clean_gstin = gstin.strip().upper()

    # Pre-validation of standard 15-digit GSTIN pattern
    if not GSTIN_REGEX.match(clean_gstin):
        return {
            "error": "invalid_gstin_format",
            "message": f"'{clean_gstin}' is not a valid 15-character GSTIN format.",
        }

    try:
        headers = get_sandbox_headers(timeout=timeout)
    except TimeoutError as te:
        return {
            "error": "api_timeout",
            "message": f"Authentication timeout connecting to GST service: {str(te)}",
        }
    except Exception as ae:
        return {
            "error": "api_error",
            "message": f"Authentication error connecting to GST service: {str(ae)}",
        }

    # Attempt lookup via GST search endpoint
    try:
        payload = {"gstin": clean_gstin}
        response = requests.post(GST_SEARCH_URL, headers=headers, json=payload, timeout=timeout)

        # Handle HTTP 404 - Not Found
        if response.status_code == 404:
            return {
                "error": "no_match_found",
                "message": f"No taxpayer record found for GSTIN: {clean_gstin}",
            }

        # If 400/422 returned, check error message
        if response.status_code in (400, 422):
            err_data = {}
            try:
                err_data = response.json()
            except Exception:
                pass
            msg = err_data.get("message", "")
            if "pattern" in msg.lower() or "invalid" in msg.lower():
                return {
                    "error": "invalid_gstin_format",
                    "message": f"GSTIN pattern rejected by API: {msg}",
                }
            if "not found" in msg.lower() or "no record" in msg.lower():
                return {
                    "error": "no_match_found",
                    "message": f"No match found for GSTIN: {clean_gstin}",
                }
            return {
                "error": "api_error",
                "message": f"API returned error {response.status_code}: {msg}",
            }

        if response.status_code != 200:
            return {
                "error": "api_error",
                "message": f"GST API returned unexpected status {response.status_code}: {response.text[:200]}",
            }

        res_json = response.json()
        payload_data = res_json.get("data", {})
        # The payload could be nested under "data"
        tp_data = payload_data.get("data", payload_data) if isinstance(payload_data, dict) else {}

        if not tp_data:
            return {
                "error": "no_match_found",
                "message": f"No taxpayer details found in response for GSTIN: {clean_gstin}",
            }

        legal_name = tp_data.get("lgnm") or tp_data.get("legalName") or ""
        trade_name = tp_data.get("tradeNam") or tp_data.get("trade_name") or legal_name
        status = tp_data.get("sts") or tp_data.get("status") or "Unknown"

        # State extraction
        pradr = tp_data.get("pradr", {})
        addr = pradr.get("addr", {}) if isinstance(pradr, dict) else {}
        state = addr.get("stcd") or tp_data.get("stateName") or addr.get("dst") or ""

        # Registration date
        registration_date = tp_data.get("rgdt") or tp_data.get("regStartDate") or ""

        return {
            "legal_name": legal_name,
            "trade_name": trade_name,
            "status": status,
            "state": state,
            "registration_date": registration_date,
        }

    except requests.exceptions.Timeout:
        return {
            "error": "api_timeout",
            "message": f"Request timed out while connecting to GST API for GSTIN: {clean_gstin}",
        }
    except requests.exceptions.RequestException as re_err:
        return {
            "error": "api_error",
            "message": f"Network or request error while querying GST API: {str(re_err)}",
        }
    except Exception as e:
        return {
            "error": "api_error",
            "message": f"Unhandled error during GST lookup: {str(e)}",
        }
