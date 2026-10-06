import re
from typing import Any, Dict, List


def analyze_screenshot_text(ocr_text: str) -> Dict[str, Any]:
    """
    Analyzes OCR text extracted from WhatsApp, Telegram, LinkedIn, or Email recruitment screenshots.
    Detects scam recruitment language and signals, returning structured evidence.
    """
    if not ocr_text:
        return {"message_signals": [], "detected_count": 0}

    signals: List[Dict[str, Any]] = []

    # 1. Upfront Payment / Fees
    payment_patterns = [
        r"(?:registration|processing|training|security|laptop|placement|certificate|uniform|documentation)\s+(?:fee|deposit|charge|amount)[^\n.]{0,40}",
        r"(?:refundable\s+deposit|security\s+deposit)\s*(?:of|is)?\s*(?:₹|INR|Rs\.?)\s*[\d,]+",
        r"(?:pay|deposit|transfer|send)\s+(?:₹|INR|Rs\.?)\s*[\d,]+",
        r"(?:fee|charge|deposit)\s*(?:of|is)?\s*(?:₹|INR|Rs\.?)\s*[\d,]+",
    ]
    payment_detected = False
    for pat in payment_patterns:
        m = re.search(pat, ocr_text, re.IGNORECASE)
        if m:
            signals.append(
                {
                    "rule": "upfront_payment",
                    "name": "Upfront Payment Demand",
                    "detected": True,
                    "evidence": m.group(0).strip(),
                    "severity": "HIGH",
                    "description": "Recruiter demands payment or deposit before employment.",
                }
            )
            payment_detected = True
            break
    if not payment_detected:
        signals.append(
            {
                "rule": "upfront_payment",
                "name": "Upfront Payment Demand",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "No registration or processing fees demanded.",
            }
        )

    # 2. Urgency and Pressure Tactics
    urgency_patterns = [
        r"(?:immediate\s+joining|urgent\s+hiring|hurry\s+up|limited\s+slots?|slots?\s+filling\s+fast)",
        r"(?:offer\s+expires\s+today|valid\s+till\s+today|last\s+day\s+to\s+apply|respond\s+within\s+\d+\s+hours?)",
        r"(?:urgent\s+requirement|immediate\s+offer|act\s+fast)",
    ]
    urgency_detected = False
    for pat in urgency_patterns:
        m = re.search(pat, ocr_text, re.IGNORECASE)
        if m:
            signals.append(
                {
                    "rule": "urgency",
                    "name": "Extreme Urgency / Pressure",
                    "detected": True,
                    "evidence": m.group(0).strip(),
                    "severity": "MEDIUM",
                    "description": "Recruiter employs artificial urgency or pressure tactics.",
                }
            )
            urgency_detected = True
            break
    if not urgency_detected:
        signals.append(
            {
                "rule": "urgency",
                "name": "Extreme Urgency / Pressure",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "No artificial urgency pressure detected.",
            }
        )

    # 3. Guaranteed Selection / No Interview
    selection_patterns = [
        r"(?:direct\s+selection|selected\s+without\s+interview|no\s+interview|100%\s+guaranteed\s+job)",
        r"(?:congratulations!?\s+you\s+(?:have\s+been|are)\s+selected|instant\s+offer\s+letter)",
        r"(?:job\s+confirmation\s+without\s+test)",
    ]
    selection_detected = False
    for pat in selection_patterns:
        m = re.search(pat, ocr_text, re.IGNORECASE)
        if m:
            signals.append(
                {
                    "rule": "guaranteed_selection",
                    "name": "Guaranteed / No-Interview Selection",
                    "detected": True,
                    "evidence": m.group(0).strip(),
                    "severity": "HIGH",
                    "description": "Candidate offered job without rigorous technical assessment or interview.",
                }
            )
            selection_detected = True
            break
    if not selection_detected:
        signals.append(
            {
                "rule": "guaranteed_selection",
                "name": "Guaranteed / No-Interview Selection",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "Standard recruitment process implied.",
            }
        )

    # 4. Unrealistic Salary Claims
    unrealistic_salary_patterns = [
        r"(?:earn\s+(?:₹|INR|Rs\.?)?\s*[\d,]+\s*(?:daily|per\s+day|per\s+hour|weekly))",
        r"(?:part[-\s]?time\s*[:\-]?\s*(?:₹|INR|Rs\.?)\s*(?:[5-9]\d{4}|\d{6,}))",
        r"(?:work\s+from\s+home\s+(?:and\s+)?earn\s+(?:₹|INR|Rs\.?)?\s*[\d,]+)",
    ]
    unrealistic_salary_detected = False
    for pat in unrealistic_salary_patterns:
        m = re.search(pat, ocr_text, re.IGNORECASE)
        if m:
            signals.append(
                {
                    "rule": "unrealistic_salary",
                    "name": "Unrealistic Compensation Claim",
                    "detected": True,
                    "evidence": m.group(0).strip(),
                    "severity": "HIGH",
                    "description": "Compensation promises disproportionate earnings for minimal commitment.",
                }
            )
            unrealistic_salary_detected = True
            break
    if not unrealistic_salary_detected:
        signals.append(
            {
                "rule": "unrealistic_salary",
                "name": "Unrealistic Compensation Claim",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "Compensation claims appear realistic or not cited.",
            }
        )

    # 5. Personal / Free Email Address
    personal_email_match = re.search(
        r"\b[A-Za-z0-9._%+-]+@(gmail|yahoo|hotmail|outlook|rediffmail|icloud)\.com\b",
        ocr_text,
        re.IGNORECASE,
    )
    if personal_email_match:
        signals.append(
            {
                "rule": "personal_email",
                "name": "Personal / Free Email Contact",
                "detected": True,
                "evidence": personal_email_match.group(0).strip(),
                "severity": "MEDIUM",
                "description": "Recruiter conducts business using an anonymous free email provider.",
            }
        )
    else:
        signals.append(
            {
                "rule": "personal_email",
                "name": "Personal / Free Email Contact",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "No personal email addresses detected.",
            }
        )

    # 6. WhatsApp or Telegram-Only Recruitment
    chat_patterns = [
        r"(?:contact\s+(?:us\s+)?(?:on|via)?\s*whatsapp|whatsapp\s+only|message\s+on\s+whatsapp\s*[:\-]?\s*[\d\+\s]+)",
        r"(?:telegram\s+channel|telegram\s+group|contact\s+on\s+telegram|t\.me\/[A-Za-z0-9_]+)",
        r"(?:dm\s+on\s+telegram|whatsapp\s+hr\s*[:\-]?\s*[\d\+\s]+)",
    ]
    chat_detected = False
    for pat in chat_patterns:
        m = re.search(pat, ocr_text, re.IGNORECASE)
        if m:
            signals.append(
                {
                    "rule": "chat_only_communication",
                    "name": "Chat-Only Recruitment Channel",
                    "detected": True,
                    "evidence": m.group(0).strip(),
                    "severity": "MEDIUM",
                    "description": "Recruitment communication restricted exclusively to encrypted chat apps.",
                }
            )
            chat_detected = True
            break
    if not chat_detected:
        signals.append(
            {
                "rule": "chat_only_communication",
                "name": "Chat-Only Recruitment Channel",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "Communication channel is not restricted to chat apps.",
            }
        )

    # 7. Sensitive Credential Requests
    sensitive_patterns = [
        r"(?:bank\s+account|atm\s+pin|upi\s+pin|otp|cvv|password|internet\s+banking)",
        r"(?:share\s+aadhaar\s+front\s+and\s+back|send\s+pan\s+card\s+photo)",
        r"(?:credit\s+card|debit\s+card|netbanking\s+credentials)",
    ]
    sensitive_detected = False
    for pat in sensitive_patterns:
        m = re.search(pat, ocr_text, re.IGNORECASE)
        if m:
            signals.append(
                {
                    "rule": "sensitive_credentials_requested",
                    "name": "Sensitive Financial/Identity Demand",
                    "detected": True,
                    "evidence": m.group(0).strip(),
                    "severity": "HIGH",
                    "description": "Suspicious request for banking details, OTP, or identity credentials.",
                }
            )
            sensitive_detected = True
            break
    if not sensitive_detected:
        signals.append(
            {
                "rule": "sensitive_credentials_requested",
                "name": "Sensitive Financial/Identity Demand",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "No requests for passwords, OTPs, or banking credentials.",
            }
        )

    # 8. Suspicious Links or Shorteners
    link_match = re.search(r"\b(?:bit\.ly|tinyurl\.com|rb\.gy|is\.gd|cutt\.ly|t\.co)\/[A-Za-z0-9_-]+\b", ocr_text, re.IGNORECASE)
    if link_match:
        signals.append(
            {
                "rule": "suspicious_links",
                "name": "Obfuscated / Shortened Link",
                "detected": True,
                "evidence": link_match.group(0).strip(),
                "severity": "MEDIUM",
                "description": "Shortened link used to conceal target domain destination.",
            }
        )
    else:
        signals.append(
            {
                "rule": "suspicious_links",
                "name": "Obfuscated / Shortened Link",
                "detected": False,
                "evidence": "None detected",
                "severity": "INFO",
                "description": "No suspicious shortened links detected.",
            }
        )

    detected_count = sum(1 for s in signals if s.get("detected"))

    return {
        "message_signals": signals,
        "detected_count": detected_count,
    }
