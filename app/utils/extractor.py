"""Entity extraction module for job postings, recruitment emails, and offer messages.

Extracts structured recruitment entities using regex patterns and heuristic NLP:
    - Company Name (with confidence scoring)
    - Domain / URL
    - Email Address
    - Phone Number
    - Stated Salary / Stipend
    - GSTIN (15-character Goods and Services Tax Identification Number)
    - CIN (21-character Corporate Identification Number)
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Pre-compiled Regex Patterns
# ---------------------------------------------------------------------------

# GSTIN: 2 digits (state code) + 10 char PAN (5 letters, 4 digits, 1 letter) + 1 digit + 1 letter (Z) + 1 alphanumeric
# Also supports general prompt format: 2 digits + 10 alphanumeric + 1 digit + 1 letter + 1 alphanumeric
GSTIN_PATTERN = re.compile(
    r"\b(?:\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z][Zz][0-9A-Z]|\d{2}[A-Za-z0-9]{10}\d[A-Za-z][A-Za-z0-9])\b",
    re.IGNORECASE,
)

# CIN: 1 letter (U/L) + 5 digits (industry code) + 2 letters (state code) + 4 digits (year) + 3 letters (type) + 6 digits (registration)
CIN_PATTERN = re.compile(
    r"\b[A-Za-z]\d{5}[A-Za-z]{2}\d{4}[A-Za-z]{3}\d{6}\b"
)

# Standard Email Pattern
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Indian & International Phone Numbers
# Matches +91 9876543210, +91-98765-43210, 9876543210, (022) 28765432, etc.
PHONE_PATTERN = re.compile(
    r"(?:(?:\+91[\s.-]?|0)?[6-9]\d{4}[\s.-]?\d{5}|\+?\d{1,3}[\s.-]?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4})\b"
)

# Web URLs (http/https)
URL_PATTERN = re.compile(
    r"\bhttps?://[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})+(?:/[^\s,;\"'<>()]*)?",
    re.IGNORECASE,
)

# Standalone Domain Names (e.g. vertexsoftware.in, tcs.com, jobshub.xyz, blogspot.com)
DOMAIN_PATTERN = re.compile(
    r"\b(?:[a-zA-Z0-9][-a-zA-Z0-9]*\.)+(?:com|in|co\.in|org|net|io|ai|tech|co|xyz|top|info|biz|dev|app|tk|ml|ga|cf|gq|gov\.in|edu\.in)\b",
    re.IGNORECASE,
)

# Free / Third-party subdomains
FREE_SUBDOMAIN_PATTERN = re.compile(
    r"\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(?:blogspot\.[a-z.]+|wixsite\.com|weebly\.com|wordpress\.com|github\.io|sites\.google\.com)\b",
    re.IGNORECASE,
)

# Salary and Stipend Patterns (₹15,000/month, ₹25,000 – ₹40,000/month, 10 LPA, etc.)
SALARY_PATTERNS = [
    re.compile(r"(?:₹|rs\.?|inr|stipend|salary|ctc|package)\s*[:\-]?\s*([₹$€]?\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|lpa|lakhs?)?\s*(?:–|-|to)\s*[₹$€]?\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|lpa|lakhs?)?(?:\s*(?:\/|\s*per\s*)(?:month|mo|pm|annum|year|yr))?)", re.IGNORECASE),
    re.compile(r"(?:₹|rs\.?|inr|stipend|salary|ctc|package)\s*[:\-]?\s*([₹$€]?\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|lpa|lakhs?|cr)?(?:\s*(?:\/|\s*per\s*)(?:month|mo|pm|annum|year|yr))?)", re.IGNORECASE),
    re.compile(r"\b(\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|lpa|lakhs?|cr)(?:\s*(?:\/|\s*per\s*)(?:month|mo|pm|annum|year|yr))?)\b", re.IGNORECASE),
    re.compile(r"\b(\d+(?:,\d+)*\s*(?:\/|\s*per\s*)(?:month|mo|pm|annum|year|yr))\b", re.IGNORECASE),
    re.compile(r"\b(?:stipend|salary)\s+of\s+([₹$€]?\s*\d+(?:,\d+)*(?:\s*(?:\/|\s*per\s*)(?:month|mo|pm))?)\b", re.IGNORECASE),
]

ROLE_PATTERNS = [
    re.compile(r"(?:selected\s+for\s+(?:a\s+|an\s+)?|role\s*[:\-]\s*|position\s*[:\-]\s*|designation\s*[:\-]\s*|hiring\s+for\s+(?:a\s+|an\s+)?)([A-Za-z0-9\s/]+?\b(?:Internship|Intern|Developer|Engineer|Executive|Associate|Manager|Specialist|Assistant|Operator|Data Entry|Analyst|Consultant)(?:\s+(?:Internship|Intern))?)", re.IGNORECASE),
    re.compile(r"\b([A-Z][a-zA-Z0-9\s/]{2,35}?\b(?:Internship|Intern|Developer|Engineer|Executive|Associate|Manager|Specialist|Analyst)(?:\s+(?:Internship|Intern))?)\b"),
]


LOCATION_PATTERNS = [
    re.compile(r"\b(Work\s+From\s+Home|WFH|Remote|Hybrid|On-site|Onsite)\b", re.IGNORECASE),
    re.compile(r"(?:location|city|base|place)\s*[:\-]\s*([A-Za-z\s]+)", re.IGNORECASE),
]


# Common Corporate Designators and Business Keywords
CORPORATE_SUFFIXES = [
    r"Pvt\.?\s*Ltd\.?",
    r"Private\s+Limited",
    r"LLP",
    r"Limited",
    r"Ltd\.?",
    r"Technologies",
    r"Technology",
    r"Solutions",
    r"Industries",
    r"Enterprises",
    r"Consulting",
    r"Services",
    r"Systems",
    r"Studios?",
    r"Robotics",
    r"Corporation",
    r"Corp\.?",
    r"Exports",
    r"Holdings",
    r"Boosters",
    r"Hub",
]

# Regex for Capitalized Multi-word Phrases ending in or containing corporate keywords
SUFFIX_REGEX_PART = "|".join(CORPORATE_SUFFIXES)
COMPANY_HEURISTIC_PATTERN = re.compile(
    rf"\b([A-Z][a-zA-Z0-9&'.-]+(?:\s+[A-Z][a-zA-Z0-9&'.-]+){{0,5}}\s+(?:{SUFFIX_REGEX_PART}))\b"
)

# Labeled Company prefixes in job postings
LABELED_COMPANY_PATTERN = re.compile(
    r"(?:Company(?:\s+Name)?|Employer|Organization|Firm|About)\s*[:\-]\s*([A-Za-z0-9&.,' -]{2,60})",
    re.IGNORECASE,
)

FREE_EMAIL_PROVIDERS = {
    "gmail.com",
    "yahoo.com",
    "yahoo.co.in",
    "hotmail.com",
    "outlook.com",
    "rediffmail.com",
    "icloud.com",
    "protonmail.com",
    "zoho.com",
}


# ---------------------------------------------------------------------------
# Extraction Logic
# ---------------------------------------------------------------------------

def _clean_company_name(name: str) -> str:
    """Normalize whitespace and strip trailing punctuation from company names."""
    if not name:
        return ""
    cleaned = re.sub(r"[\r\n\t]+", " ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"[,:;.\-_/]+$", "", cleaned).strip()
    return cleaned


def _extract_company_name(text: str, email: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    Guess company name using heuristic rules:
    1. Explicit labeled prefixes (e.g. 'Company: XYZ Pvt Ltd') -> 'high' confidence
    2. Capitalized phrases matching corporate suffixes (e.g. 'Apex Business Solutions Pvt Ltd') -> 'high' confidence
    3. Multi-word phrases near keywords -> 'low' confidence
    4. Domain-derived fallback from corporate email -> 'low' confidence
    """
    # 1. Labeled pattern: e.g. "Company: Vertex Software Solutions Pvt Ltd"
    for match in LABELED_COMPANY_PATTERN.finditer(text):
        candidate = _clean_company_name(match.group(1))
        # Filter out common false labels or very short snippets
        if len(candidate) >= 3 and not candidate.lower().startswith(("not disclosed", "confidential", "na", "n/a")):
            return candidate, "high"

    # 2. Capitalized multi-word phrase with corporate keywords
    for match in COMPANY_HEURISTIC_PATTERN.finditer(text):
        candidate = _clean_company_name(match.group(1))
        # Skip if candidate starts with noisy words
        if len(candidate) >= 4 and not candidate.lower().startswith(("the job", "this job", "our company")):
            return candidate, "high"

    # 3. Fallback: Check if corporate email is available
    if email and "@" in email:
        domain_part = email.split("@")[-1].lower()
        if domain_part not in FREE_EMAIL_PROVIDERS:
            base_name = domain_part.split(".")[0]
            # Turn vertexsoftware -> Vertexsoftware
            if len(base_name) >= 3:
                return base_name.title(), "low"

    return None, "none"


def _extract_domain_or_url(text: str, email: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    Extract domain or URL from text:
    1. Full HTTP/HTTPS URLs
    2. Subdomains (e.g. primecareerboosters.blogspot.com)
    3. Standalone domains
    4. Fallback to corporate email domain
    """
    # Check for free site builder subdomains first (e.g. blogspot.com, wixsite.com)
    subdomain_match = FREE_SUBDOMAIN_PATTERN.search(text)
    if subdomain_match:
        return subdomain_match.group(0).lower().strip(), "high"

    # Check for full URLs
    url_match = URL_PATTERN.search(text)
    if url_match:
        url = url_match.group(0).strip()
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        return domain.lower().strip(), "high"

    # Check for standalone domains
    for match in DOMAIN_PATTERN.finditer(text):
        dom = match.group(0).lower().strip()
        # Avoid matching email username+domain as standalone domain
        start_idx = match.start()
        if start_idx > 0 and text[start_idx - 1] == "@":
            continue
        return dom, "high"

    # Fallback to domain in corporate email if present
    if email and "@" in email:
        email_domain = email.split("@")[-1].lower().strip()
        if email_domain not in FREE_EMAIL_PROVIDERS:
            return email_domain, "low"

    return None, "none"


def _extract_salary(text: str) -> Tuple[Optional[str], str]:
    """Extract stated salary or stipend."""
    for pat in SALARY_PATTERNS:
        match = pat.search(text)
        if match:
            val = match.group(1) if match.groups() else match.group(0)
            cleaned = re.sub(r"\s+", " ", val).strip()
            # Normalize prefix if missing currency/context
            return cleaned, "high"

    return None, "none"


def _extract_role(text: str) -> Tuple[Optional[str], str]:
    """Extract job role or internship designation."""
    for pat in ROLE_PATTERNS:
        match = pat.search(text)
        if match:
            val = match.group(1) if match.groups() else match.group(0)
            cleaned = re.sub(r"\s+", " ", val).strip()
            cleaned = re.sub(r"\s+(?:at|in|with|for)\s*$", "", cleaned, flags=re.IGNORECASE).strip()
            if len(cleaned) >= 3:
                return cleaned, "high"
    return None, "none"


def _extract_location(text: str) -> Tuple[Optional[str], str]:
    """Extract job location or work mode."""
    for pat in LOCATION_PATTERNS:
        match = pat.search(text)
        if match:
            val = match.group(1) if match.groups() else match.group(0)
            cleaned = re.sub(r"\s+", " ", val).strip()
            if len(cleaned) >= 3:
                return cleaned, "high"
    return None, "none"


def extract_entities(raw_text: str) -> Dict[str, Any]:
    """
    Parse a pasted job offer message or email and extract structured entities.
    Delegates to the shared, unified extraction service.
    """
    from app.services.extraction_service import extract_unified_sync
    result = extract_unified_sync(raw_text)
    return result.model_dump()


