"""Unified Extraction Service for FraudJobDetector.

Provides a shared, resilient extraction pipeline for:
    - Pasted text & copied job postings
    - Uploaded screenshots & images
    - Offer letters (PDFs, DOCX, scanned documents)

Features:
    1. Text normalization & OCR artifact stitching.
    2. High-precision deterministic NLP parser for company, job title, salary,
       work mode, interview mode, contacts, experience, and registration IDs.
    3. Optional AI structured extraction client (Gemini, OpenAI, Groq, local)
       with strict JSON validation, timeout protection, and non-destructive fallback.
    4. Standardized response schema with complete backwards-compatibility.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standardized Pydantic Schemas
# ---------------------------------------------------------------------------


class UnifiedExtractionResult(BaseModel):
    # Core Company Identity
    company_name: Optional[str] = Field(None, description="Extracted corporate or employer name")
    company_name_confidence: str = Field("none", description="'high' | 'medium' | 'low' | 'none'")
    company_domain: Optional[str] = Field(None, description="Official company domain or website")
    company_domain_confidence: str = Field("none", description="'high' | 'medium' | 'low' | 'none'")
    company_address: Optional[str] = Field(None, description="Registered or office premises address")
    company_type: Optional[str] = Field(None, description="Corporate entity type (Pvt Ltd, LLP, Public, etc.)")

    # Job & Role Details
    job_title: Optional[str] = Field(None, description="Job designation, title, or internship role")
    job_title_confidence: str = Field("none", description="'high' | 'medium' | 'low' | 'none'")
    job_description: Optional[str] = Field(None, description="Brief summary or description of duties")
    job_type: Optional[str] = Field(None, description="Full-Time, Part-Time, Internship, Contract, etc.")
    work_mode: Optional[str] = Field(None, description="Remote, Work From Home, Hybrid, On-site")
    interview_mode: Optional[str] = Field(None, description="Virtual / Video, In-Person / Walk-in, Telephonic")
    job_location: Optional[str] = Field(None, description="Work location city, state, or facility")

    # Compensation & Terms
    salary: Optional[str] = Field(None, description="Salary, CTC, or remuneration")
    stipend: Optional[str] = Field(None, description="Monthly or weekly internship stipend")
    stated_salary_or_stipend: Optional[str] = Field(None, description="Primary compensation string")
    salary_confidence: str = Field("none", description="'high' | 'medium' | 'low' | 'none'")
    compensation_raw: Optional[str] = Field(None, description="Exact compensation text snippet")

    # Eligibility & Schedule
    required_experience: Optional[str] = Field(None, description="Required years or level (e.g. 0-2 years, Fresher)")
    eligibility: Optional[str] = Field(None, description="Education or degree criteria")
    application_deadline: Optional[str] = Field(None, description="Last date or deadline to apply")
    joining_date: Optional[str] = Field(None, description="Reporting or commencement date")
    offer_date: Optional[str] = Field(None, description="Date offer or appointment letter was issued")

    # Recruiter & Contacts
    recruiter_name: Optional[str] = Field(None, description="Name of sender, HR executive, or signatory")
    recruiter_email: Optional[str] = Field(None, description="Contact or recruiter email address")
    recruiter_phone: Optional[str] = Field(None, description="Contact telephone or mobile number")
    hr_department: Optional[str] = Field(None, description="Department or talent acquisition team")

    # Registration & Statutory Numbers
    gstin: Optional[str] = Field(None, description="15-character Goods and Services Tax Identification Number")
    gstin_confidence: str = Field("none", description="'high' | 'none'")
    cin: Optional[str] = Field(None, description="21-character Corporate Identification Number")
    cin_confidence: str = Field("none", description="'high' | 'none'")
    udyam_number: Optional[str] = Field(None, description="MSME Udyam registration number")

    # Risk & Scam Indicators
    payment_or_fee: Optional[str] = Field(None, description="Demanded deposit, registration, or equipment fee")
    bank_details_requested: bool = Field(False, description="Whether bank accounts or IFSC were requested")
    documents_requested: List[str] = Field(default_factory=list, description="List of required identity/academic documents")
    has_sensitive_info: bool = Field(False, description="Whether sensitive financial or personal details are requested")

    # Metadata & Pipeline Diagnostics
    extraction_method: str = Field("deterministic_nlp", description="'ai_structured' | 'deterministic_nlp' | 'hybrid'")
    raw_text: str = Field("", description="Normalized original source document text")
    raw_text_length: int = Field(0, description="Character count of normalized text")
    missing_fields: List[str] = Field(default_factory=list, description="Key fields not present in source")
    uncertain_fields: List[str] = Field(default_factory=list, description="Fields extracted with low confidence")

    # Backwards-compatibility Aliases
    role: Optional[str] = None
    role_confidence: str = "none"
    location: Optional[str] = None
    location_confidence: str = "none"
    work_location: Optional[str] = None
    employment_type: Optional[str] = None
    probation_period: Optional[str] = None
    notice_period: Optional[str] = None
    email_address: Optional[str] = None
    email_address_confidence: str = "none"
    contact_email: Optional[str] = None
    phone_number: Optional[str] = None
    phone_number_confidence: str = "none"
    domain_or_url: Optional[str] = None
    domain_or_url_confidence: str = "none"
    claimed_domain: Optional[str] = None
    stated_salary_or_stipend_confidence: str = "none"


# ---------------------------------------------------------------------------
# Pre-compiled Regex Patterns
# ---------------------------------------------------------------------------

GSTIN_PATTERN = re.compile(
    r"\b(?:\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z][Zz][0-9A-Z]|\d{2}[A-Za-z0-9]{10}\d[A-Za-z][A-Za-z0-9])\b",
    re.IGNORECASE,
)

CIN_PATTERN = re.compile(
    r"\b[A-Za-z]\d{5}[A-Za-z]{2}\d{4}[A-Za-z]{3}\d{6}\b"
)

UDYAM_PATTERN = re.compile(
    r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|in|co\.in|org|net|io|ai|tech|co|xyz|top|info|biz|dev|app|gov\.in|edu\.in|live|online|site)\b",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?:(?:\+91[\s.-]?|0)?[6-9]\d{4}[\s.-]?\d{5}|\+?\d{1,3}[\s.-]?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4})\b"
)

URL_PATTERN = re.compile(
    r"\bhttps?://[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})+(?:/[^\s,;\"'<>()]*)?",
    re.IGNORECASE,
)

FREE_SUBDOMAIN_PATTERN = re.compile(
    r"\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(?:blogspot\.[a-z.]+|wixsite\.com|weebly\.com|wordpress\.com|github\.io|sites\.google\.com)\b",
    re.IGNORECASE,
)

DOMAIN_PATTERN = re.compile(
    r"\b(?:[a-zA-Z0-9][-a-zA-Z0-9]*\.)+(?:com|in|co\.in|org|net|io|ai|tech|co|xyz|top|info|biz|dev|app|tk|ml|ga|cf|gq|gov\.in|edu\.in|me|online|site|live)\b",
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
    r"Infotech",
    r"Software",
    r"Ventures",
    r"Digital",
    r"Labs?",
    r"Network",
    r"Global",
]

SUFFIX_REGEX_PART = "|".join(CORPORATE_SUFFIXES)

COMPANY_BLACKLIST = {
    "job", "role", "position", "opening", "opportunity", "hiring", "urgent",
    "notice", "candidate", "internship", "intern", "developer", "engineer",
    "offer", "letter", "appointment", "employment", "selection", "application",
    "congratulations", "terms", "conditions", "salary", "stipend", "package",
    "dear", "hello", "hi", "mr", "ms", "dr", "subject", "regards", "sincerely",
    "work", "home", "office", "remote", "hybrid", "qualification", "experience",
    "eligibility", "responsibilities", "requirements", "description", "details",
    "we", "you", "they", "our", "the", "a", "an", "all",
}


# ---------------------------------------------------------------------------
# Text Normalization & Preprocessing
# ---------------------------------------------------------------------------


def normalize_document_text(text: str) -> str:
    """
    Cleans and standardizes raw input text from pasted content, OCR, or PDFs.
    """
    if not text or not isinstance(text, str):
        return ""

    s = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = s.replace("—", " - ").replace("–", " - ").replace("•", "\n• ")
    s = s.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")

    # Fix broken hyphenated line wraps (e.g. "compa-\nny" or "Senior-  \nDeveloper" -> "company")
    s = re.sub(r"([A-Za-z]{2,})-\s*\n\s*([A-Za-z]{2,})", r"\1\2", s)

    # Fix spaces around @ in email candidates: e.g. "careers @ tcscom" -> "careers@tcscom"
    s = re.sub(r"\b([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)", r"\1@\2", s)

    # Fix spaces around dots in email domains: e.g. "hr@company . com" -> "hr@company.com"
    s = re.sub(r"(@[A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})\b", r"\1.\2", s)

    # Fix OCR missing dot before known TLDs in emails when there is no dot yet (e.g. "recruitment@tcscom" -> "recruitment@tcs.com")
    s = re.sub(
        r"(@[a-zA-Z0-9-]{2,}?)(com|co\.in|gov\.in|edu\.in|org|net|io|ai|tech|xyz)\b(?!\.)",
        r"\1.\2",
        s,
        flags=re.IGNORECASE,
    )

    # Fix OCR URL splits: "https : / / " -> "https://"
    s = re.sub(r"https?\s*:\s*/\s*/\s*", "https://", s, flags=re.IGNORECASE)

    # Clean excessive repetitive whitespace on individual lines
    cleaned_lines = []
    for line in s.split("\n"):
        line_str = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(line_str)

    normalized = "\n".join(cleaned_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized


# ---------------------------------------------------------------------------
# Deterministic NLP Extraction Logic
# ---------------------------------------------------------------------------


def _clean_company_candidate(s: str) -> str:
    """Strips extraneous punctuation, leading prepositions, and whitespace."""
    if not s:
        return ""
    cand = re.sub(r"[\r\n\t]+", " ", s).strip()
    cand = re.sub(r"^[,\-–:|/]+", "", cand).strip()
    cand = re.sub(r"[,\-–:|/.]+$", "", cand).strip()
    # Normalize acronym prefixes like 'TCS- ' or 'TCS - '
    cand = re.sub(r"^([A-Z]{2,6})\s*[-–:]\s*", r"\1 - ", cand)
    # Remove leading prepositions accidentally matched
    cand = re.sub(r"^(?:at|with|for|our|the|a|an|by|from)\s+", "", cand, flags=re.IGNORECASE).strip()
    # Remove trailing terms and prepositional phrases (e.g. "Swiggy for Operations Lead" -> "Swiggy")
    cand = re.sub(r"\s+(?:for|as|in|with|having|which|is|are|at|from|to|where|on)\b.*$", "", cand, flags=re.IGNORECASE).strip()
    return cand


ROLE_DESIGNATION_WORDS = {
    "engineer", "developer", "architect", "designer", "analyst",
    "consultant", "associate", "executive", "manager", "specialist",
    "administrator", "officer", "coordinator", "lead", "intern", "internship",
}


def _is_valid_company_name(s: Optional[str]) -> bool:
    """Validates that candidate is a plausible business or organization name."""
    if not s or len(s) < 2 or len(s) > 70:
        return False
    lower = s.lower().strip()
    if lower in COMPANY_BLACKLIST:
        return False
    if lower.startswith(("we:", "role:", "position:", "job:", "location:", "salary:", "contact:")):
        return False
    # Reject placeholders and confidential / undisclosed employer labels
    if any(phrase in lower for phrase in [
        "confidential", "undisclosed", "unnamed", "anonymous",
        "not disclosed", "client only", "private client", "unknown"
    ]):
        return False
    if not any(c.isalpha() for c in s):
        return False

    # Check if candidate is purely a job role (e.g. "Software Engineer", "DevOps Specialist")
    # without any corporate entity suffix
    has_corp_suffix = any(
        cs.lower() in lower
        for cs in [
            "ltd", "limited", "pvt", "llp", "technologies", "technology", "solutions",
            "industries", "enterprises", "systems", "studios", "corp",
            "corporation", "holdings", "infotech", "software", "ventures",
            "labs", "network", "global", "consulting", "services"
        ]
    )
    words = lower.split()
    if not has_corp_suffix and words and words[-1] in ROLE_DESIGNATION_WORDS:
        return False

    return True


def _extract_company_name_deterministic(text: str, email: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    Extract company name using high-precision patterns:
    1. Table rows / Key-value headers (Company | Amazon, Employer: Google)
    2. Role followed by at/with <Company> ("Junior Associate at Stripe")
    3. Natural language phrasing ("join Swiggy", "Infosys is hiring")
    4. Multi-word phrases ending in corporate suffixes
    5. Document letterhead / line 1 heuristic
    6. Fallback from validated corporate email domain
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # Pattern 1: Labeled prefix or table row
    labeled_pattern = re.compile(
        r"(?:Company(?:\s+Name)?|Employer|Organization|Firm|About\s+(?:Us)?|Hiring\s+Company|Client)\s*[:|\-]\s*([A-Za-z0-9&.,' -]{2,60})",
        re.IGNORECASE,
    )
    for line in lines:
        m = labeled_pattern.search(line)
        if m:
            cand = _clean_company_candidate(m.group(1))
            if _is_valid_company_name(cand):
                return cand, "high"

    # Pattern 2: Role or employment at/with <Company>
    role_at_patterns = [
        re.compile(r"\b(?:employment\s+with|offer\s+of\s+employment\s+(?:at|with)|welcome\s+to|joining|selected\s+at)\s+([A-Z][a-zA-Z0-9&'\-]+(?:\s+[A-Z][a-zA-Z0-9&'\-]+){0,3})(?=\s+(?:for|as|in|with|having|from|to|on)\b|[.,;:!?\n]|$)", re.IGNORECASE),
        re.compile(r"\b(?:role|internship|position|associate|engineer|developer|designer|analyst|executive|manager|opportunity)\s+(?:at|with)\s+([A-Z][a-zA-Z0-9&'\-]+(?:\s+[A-Z][a-zA-Z0-9&'\-]+){0,3})(?=\s+(?:for|as|in|with|having|from|to|on)\b|[.,;:!?\n]|$)", re.IGNORECASE),
        re.compile(r"\b([A-Z][a-zA-Z0-9&'\-]+(?:\s+[A-Z][a-zA-Z0-9&'\-]+){0,3})\s+is\s+(?:hiring|looking\s+for|seeking|inviting|pleased\s+to\s+offer)\b"),
        re.compile(r"\b(?:team\s+at|careers\s+at)\s+([A-Z][a-zA-Z0-9&'\-]+(?:\s+[A-Z][a-zA-Z0-9&'\-]+){0,3})(?=\s+(?:for|as|in|with|having|from|to|on)\b|[.,;:!?\n]|$)", re.IGNORECASE),
    ]

    for pat in role_at_patterns:
        m = pat.search(text)
        if m:
            cand = _clean_company_candidate(m.group(1))
            if _is_valid_company_name(cand):
                return cand, "high"

    # Pattern 3: Multi-word phrase matching corporate suffix
    suffix_pattern = re.compile(
        rf"\b([A-Z][a-zA-Z0-9&'.-]+(?:\s+[A-Z][a-zA-Z0-9&'.-]+){{0,5}}\s+(?:{SUFFIX_REGEX_PART}))\b"
    )
    m = suffix_pattern.search(text)
    if m:
        cand = _clean_company_candidate(m.group(1))
        if _is_valid_company_name(cand):
            return cand, "high"

    # Pattern 4: Document letterhead heuristic (Check lines 1-3 if title-like and without colons)
    doc_title_keywords = {
        "offer", "letter", "appointment", "internship", "agreement",
        "contract", "confidential", "job", "description", "recruitment",
        "notice", "candidate", "date", "subject", "annexure", "summary",
        "we:", "role:", "contact:", "salary:", "dear", "hi", "urgent",
    }
    for line in lines[:3]:
        if ":" in line:
            continue
        words = line.split()
        if 1 <= len(words) <= 6 and len(line) <= 50:
            lower_line = line.lower()
            if not any(k in lower_line for k in doc_title_keywords):
                cand = _clean_company_candidate(line)
                if _is_valid_company_name(cand):
                    return cand, "medium"

    # Pattern 5: Fallback from corporate email domain (e.g. hr@wipro.com -> Wipro)
    if email and "@" in email:
        domain_part = email.split("@")[-1].lower()
        if domain_part not in FREE_EMAIL_PROVIDERS:
            base_name = domain_part.split(".")[0]
            if len(base_name) >= 3 and base_name not in {"careers", "jobs", "hiring", "apply", "recruit", "mail"}:
                return base_name.capitalize(), "low"

    return None, "none"


def _clean_role_candidate(s: str) -> str:
    if not s:
        return ""
    cand = re.sub(r"\s+", " ", s).strip()
    cand = re.sub(r"^[,\-–:|/]+", "", cand).strip()
    cand = re.sub(r"[,\-–:|/.]+$", "", cand).strip()
    # Strip leading articles
    cand = re.sub(r"^(?:the|a|an)\s+", "", cand, flags=re.IGNORECASE).strip()
    # Strip accidental prefixes
    cand = re.sub(r"^.*?the\s+post\s+of\s+", "", cand, flags=re.IGNORECASE).strip()
    cand = re.sub(r"^.*?the\s+role\s+of\s+", "", cand, flags=re.IGNORECASE).strip()
    cand = re.sub(r"^.*?\b(?:is\s+hiring\s+for|hiring\s+for|looking\s+for|seeking)\s+", "", cand, flags=re.IGNORECASE).strip()
    # Strip trailing role words
    cand = re.sub(r"\s+(?:role|position|profile|opening|post)$", "", cand, flags=re.IGNORECASE).strip()
    # Strip accidental trailing prepositions
    cand = re.sub(r"\s+(?:at|in|with|for|from|to)\s*$", "", cand, flags=re.IGNORECASE).strip()
    return cand


def _extract_job_title_deterministic(text: str) -> Tuple[Optional[str], str]:
    """Extracts job title or internship role."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # Pattern 1: Labeled prefix or table row
    labeled_pattern = re.compile(
        r"(?:Role|Position|Job\s+Title|Designation|Post|Profile)\s*[:|\-]\s*([A-Za-z0-9\s/&,.-]{3,60})",
        re.IGNORECASE,
    )
    for line in lines:
        m = labeled_pattern.search(line)
        if m:
            cand = _clean_role_candidate(m.group(1))
            if len(cand) >= 3:
                return cand, "high"

    # Pattern 2: Contextual hiring, offer, or role phrases
    context_patterns = [
        re.compile(r"\b(?:is\s+hiring\s+for|hiring\s+for|looking\s+for|seeking)\s+(?:a\s+|an\s+)?([A-Z][a-zA-Z0-9/&-]+(?:\s+[A-Z][a-zA-Z0-9/&-]+){0,4})(?=\s+(?:at|in|with|having|,|\.|\n|$))", re.IGNORECASE),
        re.compile(r"(?:offer\s+of\s+employment\s+(?:for|as)\s+(?:the\s+post\s+of\s+)?|selected\s+for\s+(?:the\s+post\s+of\s+|a\s+|an\s+)?|selected\s+as\s+(?:a\s+|an\s+)?|appointed\s+as\s+(?:a\s+|an\s+)?)([A-Za-z0-9\s/&-]{3,50}?)(?:\s+(?:at|in|with|having|,|\.|\n|$))", re.IGNORECASE),
        re.compile(r"(?:role|position)\s+at\s+[A-Za-z0-9&'\-]+\s+for\s+([A-Z][a-zA-Z0-9/&-]+(?:\s+[A-Z][a-zA-Z0-9/&-]+){0,3})(?=\s+(?:at|in|with|having|,|\.|\n|$))", re.IGNORECASE),
        re.compile(r"\b([A-Z][a-zA-Z0-9/&-]+(?:\s+[A-Z][a-zA-Z0-9/&-]+){0,4}\s+(?:Internship|Intern|Developer|Engineer|Architect|Designer|Analyst|Consultant|Associate|Executive|Manager|Specialist|Administrator|Officer|Coordinator|Lead))\b"),
    ]

    for pat in context_patterns:
        m = pat.search(text)
        if m:
            cand = _clean_role_candidate(m.group(1))
            if len(cand) >= 3:
                return cand, "high"

    return None, "none"


def _extract_salary_deterministic(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
    """
    Extracts salary, stipend, and normalized compensation.
    Returns: (salary, stipend, primary_string, confidence)
    """
    # 1. Label patterns: matches Salary, CTC, Stipend, Payout, etc.
    label_patterns = [
        re.compile(r"(?:CTC|Salary|Package|Stipend|Gross\s+Salary|Compensation|Fixed\s+Pay|Payout|Monthly\s+Payout)\s*(?:is|of|amount|will\s+be)?\s*[:|\-]?\s*([₹$€£]?\s*[\d,]+(?:\.\d+)?\s*(?:INR|Rs\.?|₹|\$|k|lpa|lakhs?|cr)?(?:\s*(?:–|-|to)\s*[₹$€£]?\s*[\d,]+(?:\.\d+)?\s*(?:INR|Rs\.?|₹|\$|k|lpa|lakhs?|cr)?)?(?:\s*(?:\/|\s*per\s*)(?:month|mo|pm|annum|year|yr))?)", re.IGNORECASE),
    ]

    for pat in label_patterns:
        m = pat.search(text)
        if m:
            val = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,;")
            if any(c.isdigit() for c in val):
                is_stipend = bool(re.search(r"\bstipend\b", m.group(0), re.IGNORECASE))
                stipend = val if is_stipend else None
                salary = None if is_stipend else val
                return salary, stipend, val, "high"

    # 2. Standalone unit patterns (LPA, Rs., INR, $, per month, etc.)
    unit_patterns = [
        re.compile(r"\b(\d+(?:\.\d+)?\s*(?:LPA|lpa|Lakhs?(?:\s*(?:per\s*annum|p\.a\.))?))\b", re.IGNORECASE),
        re.compile(r"\b((?:Rs\.?|INR|₹|\$)\s*[\d,]+(?:\.\d+)?(?:\s*(?:\/|\s*per\s*)(?:month|mo|pm|annum|year|yr))?)\b", re.IGNORECASE),
        re.compile(r"\b([\d,]+(?:\.\d+)?\s*(?:\/|\s*per\s*)(?:month|mo|pm|annum|year|yr))\b", re.IGNORECASE),
        re.compile(r"\b(\$\s*[\d,]+(?:\s*(?:\/|\s*per\s*)(?:hour|hr|year|annum|month))?)\b", re.IGNORECASE),
    ]

    for pat in unit_patterns:
        m = pat.search(text)
        if m:
            val = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,;")
            if any(c.isdigit() for c in val):
                return val, None, val, "high"

    return None, None, None, "none"


def _extract_work_mode_deterministic(text: str) -> Optional[str]:
    """Detects work mode: Remote, Hybrid, or On-site."""
    if re.search(r"\b(?:Work\s+From\s+Home|WFH|Remote|Fully\s+Remote)\b", text, re.IGNORECASE):
        return "Remote"
    if re.search(r"\b(?:Hybrid|Flexible\s+work)\b", text, re.IGNORECASE):
        return "Hybrid"
    if re.search(r"\b(?:On-site|Onsite|In-office|Work\s+from\s+office)\b", text, re.IGNORECASE):
        return "On-site"
    return None


def _extract_job_type_deterministic(text: str) -> Optional[str]:
    """Detects job employment type."""
    if re.search(r"\b(?:internship|intern)\b", text, re.IGNORECASE):
        return "Internship"
    if re.search(r"\b(?:full[-\s]?time)\b", text, re.IGNORECASE):
        return "Full-Time"
    if re.search(r"\b(?:part[-\s]?time)\b", text, re.IGNORECASE):
        return "Part-Time"
    if re.search(r"\b(?:contract|contractual)\b", text, re.IGNORECASE):
        return "Contract"
    if re.search(r"\b(?:freelance)\b", text, re.IGNORECASE):
        return "Freelance"
    return None


def _extract_interview_mode_deterministic(text: str) -> Optional[str]:
    """Detects interview mode."""
    if re.search(r"\b(?:Google\s+Meet|Zoom|MS\s+Teams|Video\s+Call|Virtual\s+Interview|Online\s+Interview)\b", text, re.IGNORECASE):
        return "Virtual / Video"
    if re.search(r"\b(?:Walk[-\s]?in|Face\s+to\s+Face|F2F|In[-\s]?person\s+Interview|Office\s+Interview)\b", text, re.IGNORECASE):
        return "In-Person / Walk-in"
    if re.search(r"\b(?:Telephonic(?:\s+Interview)?|Phone\s+Interview)\b", text, re.IGNORECASE):
        return "Telephonic"
    return None


def _extract_location_deterministic(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts job location and company premises address.
    Returns: (job_location, company_address)
    """
    job_loc = None
    comp_addr = None

    # Location label
    loc_match = re.search(
        r"(?:Job\s+Location|Work\s+Location|Location|Base\s+Location|Place\s+of\s+Work|City)\s*[:|\-]\s*([^\n\r,;|]{2,70})",
        text,
        re.IGNORECASE,
    )
    if loc_match:
        job_loc = re.sub(r"\s+", " ", loc_match.group(1)).strip().rstrip(".,;")

    # Office address label (supports ':' or 'at')
    addr_match = re.search(
        r"(?:Registered\s+Office|Corporate\s+Office|Head\s+Office|Regd\.\s*Off|Office\s+Address|Address|Premises)\s*(?:[:|\-]|at)\s*([^\n\r|]{5,100}?)(?=\.\s+[A-Z]|\.\s*$|\n|$)",
        text,
        re.IGNORECASE,
    )
    if addr_match:
        comp_addr = re.sub(r"\s+", " ", addr_match.group(1)).strip().rstrip(".,;")

    # If job_loc is not found, search for common major hubs
    if not job_loc:
        city_match = re.search(
            r"\b(Bengaluru|Bangalore|Hyderabad|Mumbai|Pune|Chennai|Delhi|New\s+Delhi|Noida|Gurgaon|Gurugram|Kolkata|Ahmedabad|Jaipur|Kochi|Chandigarh)\b",
            text,
            re.IGNORECASE,
        )
        if city_match:
            job_loc = city_match.group(1)

    return job_loc, comp_addr


def _extract_contacts_deterministic(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Extracts (recruiter_email, recruiter_phone, domain, recruiter_name).
    """
    # 1. Email
    email_match = EMAIL_PATTERN.search(text)
    email = None
    if email_match:
        cand_email = email_match.group(0).strip().rstrip(".").lower()
        if "@" in cand_email:
            email = cand_email

    # 2. Phone
    phone = None
    phone_match = PHONE_PATTERN.search(text)
    if phone_match:
        digits = re.sub(r"\D", "", phone_match.group(0))
        if len(digits) >= 10:
            phone = phone_match.group(0).strip()
    if not phone:
        masked_match = re.search(r"(?:WhatsApp|Phone|Contact|Mobile)\s*[:\-]?\s*(\+?[\d\-X\s]{10,18})", text, re.IGNORECASE)
        if masked_match:
            phone = masked_match.group(1).strip()

    # 3. Domain or URL
    domain = None
    free_sub = FREE_SUBDOMAIN_PATTERN.search(text)
    if free_sub:
        domain = free_sub.group(0).lower().strip()
    else:
        url_m = URL_PATTERN.search(text)
        if url_m:
            parsed = urlparse(url_m.group(0).strip())
            domain = (parsed.netloc or parsed.path.split("/")[0]).lower().strip()
        else:
            for dm in DOMAIN_PATTERN.finditer(text):
                d_str = dm.group(0).lower().strip()
                s_idx = dm.start()
                if s_idx > 0 and text[s_idx - 1] == "@":
                    continue
                domain = d_str
                break
    if not domain and email and "@" in email:
        email_dom = email.split("@")[-1].lower()
        if email_dom not in FREE_EMAIL_PROVIDERS:
            domain = email_dom

    # 4. Recruiter name
    recruiter_name = None
    rec_patterns = [
        r"(?:Yours\s+sincerely|Regards|Best\s+Regards|Authorized\s+Signatory|HR\s+Manager|Talent\s+Acquisition)\s*[\n\r]+\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        r"(?:Recruiter|HR\s+Executive|Contact\s+Person|Signed\s+by)\s*[:|\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
    ]
    for pat in rec_patterns:
        rm = re.search(pat, text)
        if rm:
            recruiter_name = rm.group(1).strip()
            break

    return email, phone, domain, recruiter_name


def _extract_dates_deterministic(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts (joining_date, offer_date, application_deadline)."""
    joining_date = None
    offer_date = None
    deadline = None

    j_match = re.search(
        r"(?:Date\s+of\s+Joining|Joining\s+Date|Date\s+of\s+Commencement|Reporting\s+Date|Start\s+Date|join\s+on\s+or\s+before)\s*[:|\-]?\s*([^\n\r,;]{3,35})",
        text,
        re.IGNORECASE,
    )
    if j_match and any(c.isdigit() for c in j_match.group(1)):
        joining_date = re.sub(r"\s+", " ", j_match.group(1)).strip().rstrip(".,;")

    o_match = re.search(
        r"(?:Offer\s+Date|Date\s+of\s+Offer|Dated|Issue\s+Date)\s*[:|\-]?\s*([^\n\r,;]{3,35})",
        text,
        re.IGNORECASE,
    )
    if o_match and any(c.isdigit() for c in o_match.group(1)):
        offer_date = re.sub(r"\s+", " ", o_match.group(1)).strip().rstrip(".,;")

    d_match = re.search(
        r"(?:Apply\s+(?:on\s+or\s+)?before|Deadline|Last\s+Date(?:\s+to\s+apply)?|Valid\s+(?:till|until))\s*[:|\-]?\s*([^\n\r,;]{3,35})",
        text,
        re.IGNORECASE,
    )
    if d_match and any(c.isdigit() for c in d_match.group(1)):
        deadline = re.sub(r"\s+", " ", d_match.group(1)).strip().rstrip(".,;")

    return joining_date, offer_date, deadline


def _extract_eligibility_deterministic(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts (experience_required, eligibility_criteria)."""
    exp = None
    elig = None

    exp_match = re.search(
        r"(?:Experience|Exp(?:\.)?)\s*[:|\-]\s*([^\n\r,;|]{2,50})",
        text,
        re.IGNORECASE,
    )
    if exp_match:
        exp = exp_match.group(1).strip()
    else:
        exp_nl = re.search(
            r"\b(\d+\s*(?:–|-|to)\s*\d+\s*(?:years?|yrs?)|Fresher(?:s)?|\d+\+?\s*(?:years?|yrs?)\s*(?:of\s+)?exp(?:erience)?)\b",
            text,
            re.IGNORECASE,
        )
        if exp_nl:
            exp = exp_nl.group(1).strip()

    elig_match = re.search(
        r"(?:Eligibility|Qualification|Education|Criteria)\s*[:|\-]\s*([^\n\r,;|]{2,80})",
        text,
        re.IGNORECASE,
    )
    if elig_match:
        elig = elig_match.group(1).strip()
    else:
        deg_match = re.search(
            r"\b(B\.?E\.|BE|B\.?Tech|M\.?Tech|MCA|BCA|B\.?Sc|MBA|Graduates?|Any\s+Graduate|Diploma)\b",
            text,
        )
        if deg_match:
            elig = deg_match.group(1)

    return exp, elig


def _extract_scam_signals(text: str) -> Tuple[Optional[str], bool, List[str], bool]:
    """Extracts fees demanded, bank requests, documents, and sensitive info flags."""
    payment_or_fee = None
    fee_patterns = [
        r"((?:registration|processing|training|security|laptop|placement|certificate|uniform|documentation)\s+(?:fee|deposit|charge|amount)[^\n.]{0,60})",
        r"((?:refundable\s+deposit|security\s+deposit)\s*(?:of|is)?\s*(?:₹|INR|Rs\.?)\s*[\d,]+[^\n.]{0,50})",
        r"((?:pay|deposit|transfer)\s+(?:₹|INR|Rs\.?)\s*[\d,]+[^\n.]{0,50})",
    ]
    for pat in fee_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            payment_or_fee = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,")
            break

    bank_details_requested = bool(
        re.search(r"\b(?:bank\s+account|cancelled\s+cheque|passbook|account\s+number|ifsc\s+code)\b", text, re.IGNORECASE)
    )

    documents_requested: List[str] = []
    doc_keywords = [
        ("Aadhaar Card", r"\b(?:aadhaar|aadhar)\b"),
        ("PAN Card", r"\b(?:pan\s*card|pan\s*number)\b"),
        ("Passport", r"\b(?:passport)\b"),
        ("Marksheets / Degree", r"\b(?:marksheet|degree\s+certificate|diploma|graduation\s+certificate)\b"),
        ("Experience Certificate", r"\b(?:relieving\s+letter|experience\s+certificate)\b"),
        ("Salary Slips", r"\b(?:payslip|salary\s+slip)\b"),
        ("Cancelled Cheque / Bank Details", r"\b(?:cancelled\s+cheque|bank\s+details|passbook)\b"),
    ]
    for doc_name, pat in doc_keywords:
        if re.search(pat, text, re.IGNORECASE):
            documents_requested.append(doc_name)

    has_sensitive_info = bool(
        re.search(r"\b(?:aadhaar|aadhar|pan\s*card|pan\s*number|bank\s*account|otp|one[-\s]time\s*password|upi\s*pin|atm\s*pin|cvv|password)\b", text, re.IGNORECASE)
        or re.search(r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b", text)
        or re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", text)
        or (re.search(r"\b\d{9,18}\b", text) and bank_details_requested)
    )

    return payment_or_fee, bank_details_requested, documents_requested, has_sensitive_info


def extract_deterministic(raw_text: str) -> UnifiedExtractionResult:
    """
    Executes the pure deterministic NLP extraction pipeline on normalized text.
    """
    norm_text = normalize_document_text(raw_text)
    if not norm_text:
        return UnifiedExtractionResult(
            raw_text="",
            raw_text_length=0,
            missing_fields=["company_name", "job_title", "salary", "recruiter_email"],
        )

    # 1. Statutory IDs
    gstin_m = GSTIN_PATTERN.search(norm_text)
    gstin = gstin_m.group(0).upper() if gstin_m else None
    gstin_conf = "high" if gstin else "none"

    cin_m = CIN_PATTERN.search(norm_text)
    cin = cin_m.group(0).upper() if cin_m else None
    cin_conf = "high" if cin else "none"

    udyam_m = UDYAM_PATTERN.search(norm_text)
    udyam = udyam_m.group(0).upper() if udyam_m else None

    # 2. Contacts
    email, phone, domain, recruiter_name = _extract_contacts_deterministic(norm_text)

    # 3. Company Name
    company_name, comp_conf = _extract_company_name_deterministic(norm_text, email=email)

    # 4. Job Title
    job_title, role_conf = _extract_job_title_deterministic(norm_text)

    # 5. Salary & Stipend
    salary, stipend, comp_str, sal_conf = _extract_salary_deterministic(norm_text)

    # 6. Modes & Types
    work_mode = _extract_work_mode_deterministic(norm_text)
    job_type = _extract_job_type_deterministic(norm_text)
    interview_mode = _extract_interview_mode_deterministic(norm_text)

    # 7. Locations
    job_loc, comp_addr = _extract_location_deterministic(norm_text)

    # 8. Dates & Eligibility
    joining_date, offer_date, deadline = _extract_dates_deterministic(norm_text)
    exp, elig = _extract_eligibility_deterministic(norm_text)

    # 9. Scam signals
    fee, bank_req, docs, sensitive = _extract_scam_signals(norm_text)

    # Build missing/uncertain lists
    missing = []
    if not company_name:
        missing.append("company_name")
    if not job_title:
        missing.append("job_title")
    if not comp_str:
        missing.append("salary")
    if not email and not phone:
        missing.append("contact_info")

    uncertain = []
    if comp_conf == "low":
        uncertain.append("company_name")
    if sal_conf == "low":
        uncertain.append("salary")

    return UnifiedExtractionResult(
        company_name=company_name,
        company_name_confidence=comp_conf,
        company_domain=domain,
        company_domain_confidence="high" if domain else "none",
        company_address=comp_addr,
        company_type="Private Limited" if (company_name and "pvt" in company_name.lower()) else None,
        job_title=job_title,
        job_title_confidence=role_conf,
        job_description=norm_text[:300] if len(norm_text) > 50 else None,
        job_type=job_type,
        work_mode=work_mode,
        interview_mode=interview_mode,
        job_location=job_loc,
        salary=salary,
        stipend=stipend,
        stated_salary_or_stipend=comp_str,
        salary_confidence=sal_conf,
        compensation_raw=comp_str,
        required_experience=exp,
        eligibility=elig,
        application_deadline=deadline,
        joining_date=joining_date,
        offer_date=offer_date,
        recruiter_name=recruiter_name,
        recruiter_email=email,
        recruiter_phone=phone,
        hr_department="Human Resources" if re.search(r"\b(?:HR|Human\s+Resources|Talent)\b", norm_text, re.IGNORECASE) else None,
        gstin=gstin,
        gstin_confidence=gstin_conf,
        cin=cin,
        cin_confidence=cin_conf,
        udyam_number=udyam,
        payment_or_fee=fee,
        bank_details_requested=bank_req,
        documents_requested=docs,
        has_sensitive_info=sensitive,
        extraction_method="deterministic_nlp",
        raw_text=norm_text,
        raw_text_length=len(norm_text),
        missing_fields=missing,
        uncertain_fields=uncertain,
        # Backward compatibility aliases
        role=job_title,
        role_confidence=role_conf,
        location=job_loc,
        location_confidence="high" if job_loc else "none",
        work_location=job_loc,
        employment_type=job_type,
        probation_period=re.search(r"(?:probation\s+period|probationary\s+period|probation\s+of)\s*[:|\-]?\s*([A-Za-z0-9\s]{2,30})", norm_text, re.IGNORECASE).group(1).strip().rstrip(".,") if re.search(r"(?:probation\s+period|probationary\s+period|probation\s+of)\s*[:|\-]?\s*([A-Za-z0-9\s]{2,30})", norm_text, re.IGNORECASE) else None,
        notice_period=re.search(r"(?:notice\s+period)\s*[:|\-]?\s*([A-Za-z0-9\s]{2,30})", norm_text, re.IGNORECASE).group(1).strip().rstrip(".,") if re.search(r"(?:notice\s+period)\s*[:|\-]?\s*([A-Za-z0-9\s]{2,30})", norm_text, re.IGNORECASE) else None,
        email_address=email,
        email_address_confidence="high" if email else "none",
        contact_email=email,
        phone_number=phone,
        phone_number_confidence="high" if phone else "none",
        domain_or_url=domain,
        domain_or_url_confidence="high" if domain else "none",
        claimed_domain=domain,
        stated_salary_or_stipend_confidence=sal_conf,
    )


# ---------------------------------------------------------------------------
# Optional AI Structured Extraction Layer
# ---------------------------------------------------------------------------


def _clean_ai_json_response(raw_resp: str) -> Dict[str, Any]:
    """Strips Markdown fences and safely extracts JSON object."""
    text = raw_resp.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    return json.loads(text)


async def _call_ai_extraction_async(norm_text: str) -> Optional[Dict[str, Any]]:
    """
    Queries an AI provider (Gemini, OpenAI, Groq, or OpenAI-compatible endpoint)
    if configured via environment variables. Returns parsed dict or None on failure.
    Never exposes API keys or document contents in logs.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    custom_url = os.getenv("AI_BASE_URL")

    if not any([gemini_key, openai_key, groq_key, custom_url]):
        return None

    prompt = f"""You are a professional corporate due-diligence data extractor.
Analyze the following job posting, recruitment email, or offer letter text and extract exact entities.
Return ONLY a valid JSON object with the following schema (use null if not present in text):
{{
  "company_name": "Exact official employer name or null",
  "company_domain": "Official company domain (e.g. google.com) or null",
  "company_address": "Office or registered address or null",
  "job_title": "Role designation or internship title or null",
  "job_type": "Full-Time | Part-Time | Internship | Contract or null",
  "work_mode": "Remote | Hybrid | On-site or null",
  "interview_mode": "Virtual / Video | In-Person / Walk-in | Telephonic or null",
  "job_location": "City, state or location or null",
  "salary": "Stated compensation/CTC or null",
  "stipend": "Stated stipend or null",
  "required_experience": "Experience requirement (e.g. 0-2 years, Fresher) or null",
  "eligibility": "Academic criteria or null",
  "application_deadline": "Application deadline date or null",
  "joining_date": "Joining or reporting date or null",
  "recruiter_name": "Signatory or recruiter name or null",
  "recruiter_email": "Contact email address or null",
  "recruiter_phone": "Contact phone or WhatsApp or null",
  "gstin": "15-character GSTIN if present or null",
  "cin": "21-character CIN if present or null",
  "payment_or_fee": "Demanded fee or deposit if requested or null"
}}

Rules:
1. Do not invent facts or make up data not present in text.
2. Return ONLY the JSON object. No explanation.

Text to extract:
\"\"\"
{norm_text[:4000]}
\"\"\""""

    try:
        timeout = httpx.Timeout(6.0, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if gemini_key:
                model = os.getenv("AI_MODEL", "gemini-1.5-flash")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
                }
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return _clean_ai_json_response(parts[0].get("text", ""))

            elif openai_key or custom_url or groq_key:
                endpoint = custom_url or ("https://api.groq.com/openai/v1/chat/completions" if groq_key else "https://api.openai.com/v1/chat/completions")
                api_key = groq_key or openai_key or "no-key"
                model = os.getenv("AI_MODEL", "llama-3.3-70b-versatile" if groq_key else "gpt-4o-mini")
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                }
                resp = await client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        return _clean_ai_json_response(content)

    except Exception as e:
        logger.warning(f"Optional AI extraction encountered non-fatal error: {type(e).__name__}. Falling back cleanly to deterministic parser.")

    return None


def _merge_results(deterministic: UnifiedExtractionResult, ai_data: Optional[Dict[str, Any]]) -> UnifiedExtractionResult:
    """
    Non-destructively merges deterministic extractions with AI extractions.
    Ensures verified statutory IDs and regex findings are never dropped.
    """
    if not ai_data or not isinstance(ai_data, dict):
        return deterministic

    res_dict = deterministic.model_dump()

    ai_comp = (ai_data.get("company_name") or "").strip()
    if ai_comp and _is_valid_company_name(ai_comp):
        det_comp = deterministic.company_name or ""
        # Upgrade if deterministic has none/low, or if AI provided a more comprehensive name containing det_comp
        if (
            deterministic.company_name_confidence in ("none", "low")
            or not det_comp
            or (det_comp.lower() in ai_comp.lower() and len(ai_comp) > len(det_comp))
            or (deterministic.company_name_confidence == "medium" and len(ai_comp) > len(det_comp))
        ):
            res_dict["company_name"] = ai_comp
            res_dict["company_name_confidence"] = "high"

    ai_title = (ai_data.get("job_title") or "").strip()
    if ai_title and not deterministic.job_title:
        res_dict["job_title"] = ai_title
        res_dict["job_title_confidence"] = "high"
        res_dict["role"] = ai_title
        res_dict["role_confidence"] = "high"

    ai_sal = (ai_data.get("salary") or ai_data.get("stipend") or "").strip()
    if ai_sal and not deterministic.stated_salary_or_stipend:
        res_dict["salary"] = ai_sal
        res_dict["stated_salary_or_stipend"] = ai_sal
        res_dict["salary_confidence"] = "high"
        res_dict["stated_salary_or_stipend_confidence"] = "high"

    if not res_dict.get("work_mode") and ai_data.get("work_mode"):
        res_dict["work_mode"] = str(ai_data["work_mode"]).strip()
    if not res_dict.get("job_type") and ai_data.get("job_type"):
        res_dict["job_type"] = str(ai_data["job_type"]).strip()
    if not res_dict.get("interview_mode") and ai_data.get("interview_mode"):
        res_dict["interview_mode"] = str(ai_data["interview_mode"]).strip()
    if not res_dict.get("job_location") and ai_data.get("job_location"):
        res_dict["job_location"] = str(ai_data["job_location"]).strip()
        res_dict["location"] = res_dict["job_location"]

    ai_email = (ai_data.get("recruiter_email") or "").strip().lower()
    if ai_email and not res_dict.get("recruiter_email") and "@" in ai_email:
        res_dict["recruiter_email"] = ai_email
        res_dict["email_address"] = ai_email
        res_dict["contact_email"] = ai_email
        res_dict["email_address_confidence"] = "high"

    ai_phone = (ai_data.get("recruiter_phone") or "").strip()
    if ai_phone and not res_dict.get("recruiter_phone"):
        res_dict["recruiter_phone"] = ai_phone
        res_dict["phone_number"] = ai_phone
        res_dict["phone_number_confidence"] = "high"

    ai_domain = (ai_data.get("company_domain") or "").strip().lower()
    if ai_domain and not res_dict.get("company_domain"):
        res_dict["company_domain"] = ai_domain
        res_dict["domain_or_url"] = ai_domain
        res_dict["claimed_domain"] = ai_domain
        res_dict["company_domain_confidence"] = "high"

    if not res_dict.get("recruiter_name") and ai_data.get("recruiter_name"):
        res_dict["recruiter_name"] = str(ai_data["recruiter_name"]).strip()
    if not res_dict.get("company_address") and ai_data.get("company_address"):
        res_dict["company_address"] = str(ai_data["company_address"]).strip()

    missing = []
    if not res_dict.get("company_name"):
        missing.append("company_name")
    if not res_dict.get("job_title"):
        missing.append("job_title")
    if not res_dict.get("stated_salary_or_stipend"):
        missing.append("salary")
    res_dict["missing_fields"] = missing
    res_dict["extraction_method"] = "hybrid"

    return UnifiedExtractionResult(**res_dict)


# ---------------------------------------------------------------------------
# Public Extraction Entry Points
# ---------------------------------------------------------------------------


def extract_unified_sync(raw_text: str) -> UnifiedExtractionResult:
    """
    Synchronous unified extraction pipeline using high-precision deterministic NLP.
    Never fails or throws unhandled exceptions on messy input.
    """
    return extract_deterministic(raw_text)


async def extract_unified_async(raw_text: str) -> UnifiedExtractionResult:
    """
    Asynchronous unified extraction pipeline. Runs deterministic extraction,
    then executes AI extraction if configured, merging results non-destructively.
    """
    det = extract_deterministic(raw_text)
    try:
        ai_data = await _call_ai_extraction_async(det.raw_text)
        if ai_data:
            return _merge_results(det, ai_data)
    except Exception:
        pass
    return det
