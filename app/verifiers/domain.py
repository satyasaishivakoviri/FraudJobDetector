import re
import socket
import ssl
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import whois

# Common WHOIS privacy indicators
PRIVACY_KEYWORDS = [
    "privacy",
    "whoisguard",
    "proxy",
    "redacted",
    "withheld",
    "contact privacy",
    "gdpr",
    "identity protect",
    "private whois",
    "protection",
]


def normalize_domain(domain_input: str) -> str:
    """
    Normalize domain input by stripping protocols (http://, https://),
    paths, query parameters, port numbers, and surrounding whitespace.
    """
    if not isinstance(domain_input, str):
        return ""
    cleaned = domain_input.strip()
    if not cleaned:
        return ""

    # Prepend // if no scheme is specified so urllib.parse correctly parses the network location
    if not (cleaned.startswith("http://") or cleaned.startswith("https://") or cleaned.startswith("//")):
        cleaned = "//" + cleaned

    parsed = urllib.parse.urlparse(cleaned)
    host = parsed.netloc or parsed.path

    # Strip port if present (e.g., example.com:8080)
    host = host.split(":")[0]

    # Strip path or trailing slashes that might be retained
    host = host.split("/")[0].strip().lower()

    # Strip leading/trailing dots or whitespace
    host = host.strip(".").strip()
    return host


def check_ssl_certificate(domain: str, port: int = 443, timeout: float = 5.0) -> str:
    """
    Inspect SSL certificate on port 443.
    Returns: 'valid', 'expired', 'self-signed', 'invalid', or 'unavailable'.
    """
    if not domain or "." not in domain:
        return "unavailable"

    # Step 1: Try default verified TLS handshake
    context = ssl.create_default_context()
    try:
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                if not cert or "notAfter" not in cert:
                    return "invalid"

                not_after_str = cert["notAfter"]
                exp_date = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp_date:
                    return "expired"
                return "valid"

    except ssl.SSLCertVerificationError as e:
        msg = str(e).lower()
        if "self signed" in msg or "self-signed" in msg:
            return "self-signed"
        if "expired" in msg or "certificate has expired" in msg:
            return "expired"
        return "self-signed" if "self" in msg else "invalid"

    except ssl.SSLError as e:
        msg = str(e).lower()
        if "self signed" in msg or "self-signed" in msg:
            return "self-signed"
        if "expired" in msg:
            return "expired"
        return "invalid"

    except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError):
        return "unavailable"

    except Exception:
        return "unavailable"


def _extract_creation_date(w_obj: Any) -> Optional[datetime]:
    """
    Safely extract and parse the creation/registration date from WHOIS response.
    """
    raw_date = getattr(w_obj, "creation_date", None)
    if raw_date is None and isinstance(w_obj, dict):
        raw_date = w_obj.get("creation_date")

    if isinstance(raw_date, list):
        # Pick the earliest valid datetime in list
        dates = [d for d in raw_date if isinstance(d, datetime)]
        if dates:
            return min(dates)
        raw_date = raw_date[0] if raw_date else None

    if isinstance(raw_date, datetime):
        return raw_date

    if isinstance(raw_date, str):
        # Attempt ISO or common format parsing
        try:
            from dateutil import parser
            return parser.parse(raw_date)
        except Exception:
            return None

    return None


def _extract_registrant_org(w_obj: Any) -> Tuple[Optional[str], bool]:
    """
    Extract the registrant organization name and determine if WHOIS privacy is active.
    Returns: (registrant_org, is_privacy_protected)
    """
    org = getattr(w_obj, "org", None)
    if not org and isinstance(w_obj, dict):
        org = w_obj.get("org") or w_obj.get("registrant_organization")

    if not org:
        org = getattr(w_obj, "registrant_organization", None)

    if isinstance(org, list):
        org = org[0] if org else None

    org_str = str(org).strip() if org else ""

    # Check for privacy protection indicators in org or text
    is_privacy = False
    if org_str:
        lower_org = org_str.lower()
        if any(keyword in lower_org for keyword in PRIVACY_KEYWORDS):
            is_privacy = True
    else:
        # Check raw text for privacy flags
        raw_text = str(getattr(w_obj, "text", "")).lower()
        if any(keyword in raw_text for keyword in PRIVACY_KEYWORDS):
            is_privacy = True

    final_org = org_str if org_str else None
    return final_org, is_privacy


def check_domain(domain: str, ssl_timeout: float = 5.0) -> Dict[str, Any]:
    """
    Retrieve WHOIS information and check SSL certificate status for a domain.

    Returns a consistent dictionary:
        - domain: str (normalized domain name)
        - domain_age_days: int or None
        - registrant_org: str or None
        - ssl_status: str ('valid', 'expired', 'self-signed', 'invalid', 'unavailable')
        - ssl_certificate_status: str (alias for ssl_status)
        - is_privacy_protected: bool
        - creation_date: str (ISO format 'YYYY-MM-DD') or None
        - status: str ('success', 'partial', 'error')
        - error: str or None
    """
    normalized = normalize_domain(domain)

    if not normalized or "." not in normalized or len(normalized) < 3:
        return {
            "domain": normalized or str(domain),
            "domain_age_days": None,
            "registrant_org": None,
            "ssl_status": "unavailable",
            "ssl_certificate_status": "unavailable",
            "is_privacy_protected": False,
            "creation_date": None,
            "status": "error",
            "error": "Invalid or malformed domain name.",
        }

    # 1. SSL Certificate Verification
    ssl_status = check_ssl_certificate(normalized, timeout=ssl_timeout)

    # 2. WHOIS Information Retrieval
    domain_age_days: Optional[int] = None
    creation_date_str: Optional[str] = None
    registrant_org: Optional[str] = None
    is_privacy = False
    whois_error: Optional[str] = None

    try:
        w = whois.whois(normalized)
        if w:
            c_date = _extract_creation_date(w)
            if c_date:
                # Ensure timezone awareness for consistent delta calculation
                now = datetime.now(timezone.utc)
                if c_date.tzinfo is not None:
                    c_date_utc = c_date.astimezone(timezone.utc)
                else:
                    c_date_utc = c_date.replace(tzinfo=timezone.utc)

                delta_days = (now - c_date_utc).days
                domain_age_days = max(0, delta_days)
                creation_date_str = c_date_utc.strftime("%Y-%m-%d")

            registrant_org, is_privacy = _extract_registrant_org(w)

            # If org was empty but privacy detected, label appropriately
            if is_privacy and not registrant_org:
                registrant_org = "Privacy Protected"

    except Exception as e:
        whois_error = f"WHOIS lookup failed: {type(e).__name__}"

    # Determine overall status
    if domain_age_days is not None and ssl_status != "unavailable":
        overall_status = "success"
    elif domain_age_days is not None or ssl_status in ("valid", "expired", "self-signed"):
        overall_status = "partial"
    else:
        overall_status = "error" if whois_error else "partial"

    return {
        "domain": normalized,
        "domain_age_days": domain_age_days,
        "registrant_org": registrant_org,
        "ssl_status": ssl_status,
        "ssl_certificate_status": ssl_status,
        "is_privacy_protected": is_privacy,
        "creation_date": creation_date_str,
        "status": overall_status,
        "error": whois_error,
    }
