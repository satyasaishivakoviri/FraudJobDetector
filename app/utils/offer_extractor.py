import re
from typing import Any, Dict, List, Optional
from app.services.extraction_service import extract_unified_sync


def extract_offer_letter_data(raw_text: str) -> Dict[str, Any]:
    """
    Extracts structured offer letter attributes using the unified extraction service.
    Adheres strictly to the principle: never invent missing values.
    """
    if not raw_text or not isinstance(raw_text, str):
        return {
            "company_name": None,
            "company_address": None,
            "cin": None,
            "gstin": None,
            "udyam_number": None,
            "job_title": None,
            "salary": None,
            "stipend": None,
            "joining_date": None,
            "offer_date": None,
            "recruiter_name": None,
            "recruiter_email": None,
            "recruiter_phone": None,
            "company_domain": None,
            "hr_department": None,
            "work_location": None,
            "probation_period": None,
            "employment_type": None,
            "notice_period": None,
            "payment_or_fee": None,
            "bank_details_requested": False,
            "documents_requested": [],
            "has_sensitive_info": False,
        }

    return extract_unified_sync(raw_text).model_dump()
