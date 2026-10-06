"""Pydantic schemas and models for temporary shareable verification reports."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationReport(BaseModel):
    id: Optional[int] = None
    verification_id: str = Field(..., description="Unique corporate verification identifier (e.g. VER-2026-00182)")
    report_token: str = Field(..., description="Cryptographically secure URL-safe report token")
    sanitized_report_data: Dict[str, Any] = Field(..., description="Vetted, non-sensitive report findings")
    created_at: str = Field(..., description="Report creation timestamp (ISO)")
    expires_at: str = Field(..., description="Report expiration timestamp (ISO, 7 days from creation)")
    is_active: bool = Field(True, description="Whether the report is active and publicly viewable")


class CreateShareReportRequest(BaseModel):
    verification_id: Optional[str] = None
    report_data: Optional[Dict[str, Any]] = None


class CreateShareReportResponse(BaseModel):
    verification_id: str
    share_url: str
    report_token: str
    revoke_token: str
    expires_at: str


class RevokeShareReportRequest(BaseModel):
    revoke_token: Optional[str] = None


class VerifyJobExtensionRequest(BaseModel):
    source: Optional[str] = Field("generic", description="Origin source e.g. linkedin, indeed, naukri, web")
    job_title: Optional[str] = None
    company_name: str = Field(..., min_length=1, description="Company name extracted or entered by user")
    job_description: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    employment_type: Optional[str] = None
    application_url: Optional[str] = None
    company_domain: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_phone: Optional[str] = None
    visible_fee_info: Optional[str] = None
