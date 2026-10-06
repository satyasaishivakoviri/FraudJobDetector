import base64
import datetime
import io
import os
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
from pydantic import BaseModel, Field

from app.database import (
    create_shareable_report,
    get_shareable_report,
    init_db,
    revoke_shareable_report,
)
from app.models.report import (
    CreateShareReportRequest,
    CreateShareReportResponse,
    RevokeShareReportRequest,
    VerifyJobExtensionRequest,
)
from app.services.extraction_service import extract_unified_async, extract_unified_sync
from app.services.verification_service import verify_company
from app.utils.document_parser import (
    DocumentValidationError,
    parse_uploaded_document,
)
from app.utils.extractor import extract_entities
from app.utils.matching import match_company_name
from app.utils.offer_extractor import extract_offer_letter_data
from app.utils.screenshot_analyzer import analyze_screenshot_text
from app.verifiers.domain import check_domain
from app.verifiers.gst import lookup_gst
from app.verifiers.mca import lookup_mca
from app.verifiers.udyam import lookup_udyam


# Load environment variables
load_dotenv()

# Initialize SQLite database for reports (deferred gracefully if filesystem is constrained)
try:
    init_db()
except Exception as _e:
    pass

app = FastAPI(
    title="Fraud Job Detector API",
    description="Automated business verification and fraud risk scoring engine for job postings",
    version="1.2.0",
)

# Enable CORS for frontend and browser extension integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Schemas & Data Models
# ---------------------------------------------------------------------------


class UploadedDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_type: str
    file_size: int
    document_type: str
    extracted_text: str
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class ExtractedOfferData(BaseModel):
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    cin: Optional[str] = None
    gstin: Optional[str] = None
    udyam_number: Optional[str] = None
    job_title: Optional[str] = None
    salary: Optional[str] = None
    stipend: Optional[str] = None
    joining_date: Optional[str] = None
    offer_date: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_phone: Optional[str] = None
    company_domain: Optional[str] = None
    work_location: Optional[str] = None


class VerificationSnapshot(BaseModel):
    risk_score: int
    risk_level: str
    mca_status: Optional[str] = None
    gst_status: Optional[str] = None
    udyam_status: Optional[str] = None
    domain_status: Optional[str] = None
    company_match_score: Optional[float] = None
    verified_at: str


class ExtractEntitiesRequest(BaseModel):
    text: Optional[str] = Field(None, description="Pasted job offer message or email text")
    message: Optional[str] = Field(None, description="Alternative field for message text")


class ExtractEntitiesResponse(BaseModel):
    company_name: Optional[str] = None
    company_name_confidence: str = "none"
    company_domain: Optional[str] = None
    company_domain_confidence: str = "none"
    company_address: Optional[str] = None
    domain_or_url: Optional[str] = None
    domain_or_url_confidence: str = "none"
    claimed_domain: Optional[str] = None
    email_address: Optional[str] = None
    email_address_confidence: str = "none"
    contact_email: Optional[str] = None
    recruiter_email: Optional[str] = None
    phone_number: Optional[str] = None
    phone_number_confidence: str = "none"
    recruiter_phone: Optional[str] = None
    stated_salary_or_stipend: Optional[str] = None
    stated_salary_or_stipend_confidence: str = "none"
    salary: Optional[str] = None
    salary_confidence: str = "none"
    stipend: Optional[str] = None
    gstin: Optional[str] = None
    gstin_confidence: str = "none"
    cin: Optional[str] = None
    cin_confidence: str = "none"
    udyam_number: Optional[str] = None
    role: Optional[str] = None
    role_confidence: str = "none"
    job_title: Optional[str] = None
    job_title_confidence: str = "none"
    job_type: Optional[str] = None
    work_mode: Optional[str] = None
    interview_mode: Optional[str] = None
    job_location: Optional[str] = None
    location: Optional[str] = None
    location_confidence: str = "none"
    required_experience: Optional[str] = None
    eligibility: Optional[str] = None
    application_deadline: Optional[str] = None
    joining_date: Optional[str] = None
    offer_date: Optional[str] = None
    recruiter_name: Optional[str] = None
    hr_department: Optional[str] = None
    payment_or_fee: Optional[str] = None
    has_sensitive_info: bool = False
    extraction_method: str = "deterministic_nlp"
    raw_text_length: int = 0
    missing_fields: List[str] = Field(default_factory=list)
    uncertain_fields: List[str] = Field(default_factory=list)


class CheckCompanyRequest(BaseModel):
    company_name: str = Field(..., min_length=1, description="Claimed company name (required)")
    claimed_domain: Optional[str] = Field(None, description="Claimed company website domain (optional)")
    gstin: Optional[str] = Field(None, description="15-character GSTIN (optional)")
    contact_email: Optional[str] = Field(None, description="Recruiter contact email (optional)")
    job_message: Optional[str] = Field(None, description="Original job offer message or email text (optional)")
    description: Optional[str] = Field(None, description="Original job message / description (optional)")
    notes: Optional[str] = Field(None, description="Additional context or notes (optional)")
    offer_data: Optional[Dict[str, Any]] = Field(None, description="Extracted offer letter metadata (optional)")
    previous_result: Optional[Dict[str, Any]] = Field(None, description="Previous verification result for diffing (optional)")
    input_source: Optional[str] = Field("message", description="Input type: 'message', 'offer_letter', or 'screenshot'")


class RecheckCompanyRequest(BaseModel):
    company_name: str = Field(..., min_length=1, description="Claimed company name")
    claimed_domain: Optional[str] = None
    gstin: Optional[str] = None
    contact_email: Optional[str] = None
    job_message: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    offer_data: Optional[Dict[str, Any]] = None
    previous_result: Optional[Dict[str, Any]] = None
    input_source: Optional[str] = "recheck"


class CheckCompanyResponse(BaseModel):
    verification_id: Optional[str] = Field(None, description="Unique verification identifier")
    risk_score: int = Field(..., description="Cumulative fraud risk score")
    risk_level: str = Field(..., description="Risk level: 'LOW' (0-20), 'MEDIUM' (21-50), 'HIGH' (51+)")
    reasons: List[Any] = Field(default_factory=list, description="List of triggered risk reason objects or descriptions")
    triggered_rules: Optional[List[Dict[str, Any]]] = None
    mca_result: Optional[Dict[str, Any]] = None
    gst_result: Optional[Dict[str, Any]] = None
    udyam_result: Optional[Dict[str, Any]] = None
    domain_result: Optional[Dict[str, Any]] = None
    matching_result: Optional[Dict[str, Any]] = None
    company_match: Optional[Dict[str, Any]] = None
    company_identity: Optional[Dict[str, Any]] = None
    safety_recommendations: List[Any] = Field(
        default_factory=list,
        description="Actionable safety recommendations based on detected risk signals",
    )
    mca: Optional[Dict[str, Any]] = Field(None, description="MCA verification result with source metadata")
    gst: Optional[Dict[str, Any]] = Field(None, description="GST verification result with source metadata")
    udyam: Optional[Dict[str, Any]] = Field(None, description="Udyam verification result with source metadata")
    domain: Optional[Dict[str, Any]] = Field(None, description="Domain verification result with source metadata")
    offer_letter_consistency: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Consistency comparison items between offer claims and registry findings"
    )
    input_source: Optional[str] = "message"
    verified_at: Optional[str] = None
    verified_at_iso: Optional[str] = None
    verification_changes: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Itemized changes detected since previous verification"
    )
    has_changes: bool = False


class MatchRequest(BaseModel):
    claimed_name: str
    registry_results: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Extraction Endpoint: POST /extract-entities & POST /extract-job-info
# ---------------------------------------------------------------------------


@app.post(
    "/extract-entities",
    response_model=ExtractEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract entities from pasted job offer or email",
    description=(
        "Parses a pasted job offer message or email using regex and heuristics to extract "
        "company name, domain, email, phone, salary, GSTIN, and CIN with confidence flags."
    ),
)
@app.post(
    "/extract-job-info",
    response_model=ExtractEntitiesResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def extract_entities_route(request: ExtractEntitiesRequest) -> ExtractEntitiesResponse:
    content = (request.text or request.message or "").strip()
    result = await extract_unified_async(content)
    return ExtractEntitiesResponse(**result.model_dump())


# ---------------------------------------------------------------------------
# Upload Endpoints: Offer Letter & Screenshot
# ---------------------------------------------------------------------------


@app.post(
    "/upload/offer-letter",
    status_code=status.HTTP_200_OK,
    summary="Upload and scan offer letter (PDF, DOCX, JPG, PNG)",
    description=(
        "Accepts offer letter documents up to 10MB. Extracts digital text or runs OCR on scanned pages, "
        "parses structured offer attributes, checks for fees and sensitive document requests."
    ),
)
@app.post(
    "/upload-offer-letter",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def upload_offer_letter(file: UploadFile = File(...)):
    filename = file.filename or "offer_letter.pdf"
    content = await file.read()

    try:
        parsed = parse_uploaded_document(filename, content, "offer_letter")
    except DocumentValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process offer letter: {str(e)}",
        )

    unified_res = await extract_unified_async(parsed["raw_text"])
    extracted_offer = unified_res.model_dump()

    return {
        "success": True,
        "filename": filename,
        "file_size": parsed["file_size"],
        "file_type": parsed["file_type"],
        "raw_text": parsed["raw_text"],
        "extracted_text": parsed["raw_text"],
        "confidence": parsed["confidence"],
        "low_confidence": parsed["low_confidence"],
        "extracted_data": extracted_offer,
        "offer_data": extracted_offer,
        "extracted_entities": extracted_offer,
        "has_sensitive_info": extracted_offer.get("has_sensitive_info", False),
    }


@app.post(
    "/upload/screenshot",
    status_code=status.HTTP_200_OK,
    summary="Upload and analyze recruitment screenshot (PNG, JPG, WEBP)",
    description=(
        "Performs native OCR on WhatsApp, Telegram, LinkedIn, or Email screenshots. "
        "Computes confidence, extracts entities, and detects AI scam recruitment patterns."
    ),
)
@app.post(
    "/analyze-screenshot",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def upload_screenshot(file: UploadFile = File(...)):
    filename = file.filename or "screenshot.png"
    content = await file.read()

    try:
        parsed = parse_uploaded_document(filename, content, "screenshot")
    except DocumentValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process screenshot: {str(e)}",
        )

    # Generate safe thumbnail data URI for Screen 2 preview
    preview_data_url = None
    try:
        with Image.open(io.BytesIO(content)) as im:
            thumb = im.copy()
            thumb.thumbnail((500, 500))
            if thumb.mode in ("RGBA", "P"):
                thumb = thumb.convert("RGB")
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            preview_data_url = f"data:image/jpeg;base64,{b64_str}"
    except Exception:
        pass

    unified_res = await extract_unified_async(parsed["raw_text"])
    extracted_entities = unified_res.model_dump()
    screenshot_signals = analyze_screenshot_text(parsed["raw_text"])

    return {
        "success": True,
        "filename": filename,
        "file_size": parsed["file_size"],
        "file_type": parsed["file_type"],
        "raw_text": parsed["raw_text"],
        "confidence": parsed["confidence"],
        "low_confidence": parsed["low_confidence"],
        "extracted_entities": extracted_entities,
        "extracted_data": extracted_entities,
        "offer_data": extracted_entities,
        "message_signals": screenshot_signals.get("message_signals", []),
        "detected_count": screenshot_signals.get("detected_count", 0),
        "image_preview_url": preview_data_url,
    }


# ---------------------------------------------------------------------------
# Core Endpoint: POST /check-company
# ---------------------------------------------------------------------------


@app.post(
    "/check-company",
    response_model=CheckCompanyResponse,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive Company Verification & Fraud Risk Evaluation",
    description=(
        "Verifies a company across MCA, GST, Udyam, and Domain/WHOIS. Performs fuzzy matching "
        "and calculates cumulative fraud risk score, safety recommendations, and offer consistency."
    ),
)
def check_company_endpoint(request: CheckCompanyRequest) -> CheckCompanyResponse:
    company_name = request.company_name.strip()
    if not company_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="company_name cannot be blank.",
        )

    try:
        result = verify_company(
            company_name=company_name,
            claimed_domain=request.claimed_domain,
            gstin=request.gstin,
            contact_email=request.contact_email,
            job_message=request.job_message,
            description=request.description,
            notes=request.notes,
            offer_data=request.offer_data,
            previous_result=request.previous_result,
            input_source=request.input_source or "message",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}",
        )

    return CheckCompanyResponse(**result)


# ---------------------------------------------------------------------------
# Recheck Endpoint: POST /recheck-company
# ---------------------------------------------------------------------------


@app.post(
    "/recheck-company",
    response_model=CheckCompanyResponse,
    status_code=status.HTTP_200_OK,
    summary="Recheck company verification with live queries and change diffing",
    description=(
        "Re-runs MCA, GST, Udyam, and Domain checks using the shared verification service. "
        "Recalculates risk score, updates server timestamp, and returns itemized changes."
    ),
)
def recheck_company_endpoint(request: RecheckCompanyRequest) -> CheckCompanyResponse:
    company_name = request.company_name.strip()
    if not company_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="company_name cannot be blank.",
        )

    try:
        result = verify_company(
            company_name=company_name,
            claimed_domain=request.claimed_domain,
            gstin=request.gstin,
            contact_email=request.contact_email,
            job_message=request.job_message,
            description=request.description,
            notes=request.notes,
            offer_data=request.offer_data,
            previous_result=request.previous_result,
            input_source=request.input_source or "recheck",
            verification_id=request.previous_result.get("verification_id") if request.previous_result else None,
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recheck failed: {str(e)}",
        )

    return CheckCompanyResponse(**result)


# ---------------------------------------------------------------------------
# UI Page Routes (3 Completely Separate Screens)
# Screen 1: / (Message / Document Submission)
# Screen 2: /review (Entity Review & Editing)
# Screen 3: /results (Verification Report & Recheck)
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
@app.get("/paste", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
def serve_index_page():
    """Screen 1: Submission page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Index page not found at " + frontend_path}


@app.get("/review", include_in_schema=False)
def serve_review_page():
    """Screen 2: Entity Review & Editing page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "review.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Review page not found at " + frontend_path}


@app.get("/results", include_in_schema=False)
@app.get("/risk-management", include_in_schema=False)
@app.get("/risk", include_in_schema=False)
def serve_results_page():
    """Screen 3: Verification Report & Recheck page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "results.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Results page not found at " + frontend_path}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/verify/gst/{gstin}")
def verify_gst(gstin: str):
    """Verify business registration details by GSTIN."""
    return lookup_gst(gstin)


@app.get("/verify/mca")
def verify_mca(company_name: str = Query(..., description="Company name to search in MCA")):
    """Verify company incorporation details and status by company name."""
    return lookup_mca(company_name)


@app.get("/verify/udyam")
def verify_udyam(query: str = Query(..., description="Company name or Udyam Registration Number")):
    """Verify MSME/Udyam registration for a company or Udyam number."""
    return lookup_udyam(query)


@app.get("/verify/domain")
def verify_domain(domain: str = Query(..., description="Domain name or URL to check")):
    """Check domain WHOIS age, registrant organization, and SSL certificate."""
    return check_domain(domain)


@app.post("/match/company")
def match_company(request: MatchRequest):
    """Match a claimed company name against candidate registry results using fuzzy matching."""
    return match_company_name(request.claimed_name, request.registry_results)


# ---------------------------------------------------------------------------
# Feature 1: Browser Extension Endpoint
# ---------------------------------------------------------------------------


@app.post(
    "/extension/verify-job",
    summary="Browser Extension Job Verification",
    description="Analyzes public job posting content extracted by browser extension and returns compact fraud risk indicators.",
)
def extension_verify_job(request: VerifyJobExtensionRequest):
    """Verifies a job posting extracted or entered via the browser extension."""
    company_name = request.company_name.strip()
    if not company_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="company_name cannot be blank.",
        )

    # Consolidate job context text for risk evaluation
    message_parts = []
    if request.job_title:
        message_parts.append(f"Job Title: {request.job_title}")
    if request.job_description:
        message_parts.append(request.job_description)
    if request.visible_fee_info:
        message_parts.append(f"Fee/Payment details: {request.visible_fee_info}")
    if request.location:
        message_parts.append(f"Location: {request.location}")
    if request.salary:
        message_parts.append(f"Salary: {request.salary}")
    if request.employment_type:
        message_parts.append(f"Type: {request.employment_type}")
    if request.recruiter_name:
        message_parts.append(f"Recruiter: {request.recruiter_name}")

    consolidated_message = "\n".join(message_parts)

    try:
        result = verify_company(
            company_name=company_name,
            claimed_domain=request.company_domain,
            contact_email=request.recruiter_email,
            job_message=consolidated_message,
            description=request.job_description,
            notes=f"Source: {request.source} | URL: {request.application_url or 'N/A'}",
            input_source="browser_extension",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extension verification failed: {str(e)}",
        )

    # Create temporary shareable report so clicking 'Open Full Report' loads seamlessly
    report_token = None
    share_url = None
    full_report_url = "/results"
    try:
        share_info = create_shareable_report(result, ttl_days=7)
        report_token = share_info["report_token"]
        share_url = f"/report/{report_token}"
        full_report_url = f"/results?token={report_token}"
    except Exception:
        pass

    warning_signals = []
    for r in result.get("reasons", []):
        if isinstance(r, dict):
            warning_signals.append(r.get("reason", "") or r.get("description", ""))
        elif isinstance(r, str):
            warning_signals.append(r)

    return {
        "risk_level": result["risk_level"],
        "risk_score": result["risk_score"],
        "company_name": company_name,
        "verification_id": result.get("verification_id"),
        "warning_signals": warning_signals,
        "safety_recommendations": result.get("safety_recommendations", []),
        "verified_at": result.get("verified_at"),
        "report_token": report_token,
        "share_url": share_url,
        "full_report_url": full_report_url,
        "full_result": result,
    }


# ---------------------------------------------------------------------------
# Feature 3: Temporary Shareable Verification Report Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/create-share-report",
    response_model=CreateShareReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a temporary, sanitized shareable verification report",
    description="Generates a cryptographically secure 7-day share link with all private data stripped.",
)
def create_share_report_endpoint(request: CreateShareReportRequest):
    """Creates a temporary public snapshot report valid for 7 days."""
    if not request.report_data or not isinstance(request.report_data, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="report_data dictionary is required.",
        )

    report_payload = dict(request.report_data)
    if request.verification_id:
        report_payload["verification_id"] = request.verification_id

    try:
        report_info = create_shareable_report(report_payload, ttl_days=7)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create shareable report: {str(e)}",
        )

    token = report_info["report_token"]
    share_url = f"/report/{token}"

    return CreateShareReportResponse(
        verification_id=report_info["verification_id"],
        share_url=share_url,
        report_token=token,
        revoke_token=report_info["revoke_token"],
        expires_at=report_info["expires_at"],
    )


@app.get(
    "/api/report/{report_token}",
    summary="Get sanitized verification report JSON",
    description="Fetches sanitized verification findings if report is active and not expired.",
)
def get_report_json(report_token: str):
    """Public JSON endpoint for fetching a sanitized verification report."""
    clean_token = report_token.strip()
    status_result, report_data = get_shareable_report(clean_token)

    if status_result == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification report not found or invalid token.",
        )
    elif status_result == "expired":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This verification report has expired. Reports are automatically expired after 7 days.",
        )
    elif status_result == "revoked":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This verification report has been revoked by the owner.",
        )

    return report_data


@app.get(
    "/report/{report_token}",
    summary="View shareable verification report",
    description="Serves the public report page (HTML) or sanitized JSON based on Accept header.",
)
def view_share_report_endpoint(report_token: str, request: Request):
    """Serves the standalone public report HTML for browser requests or JSON otherwise."""
    accept = request.headers.get("accept", "").lower()
    if "text/html" in accept or "*/*" in accept and "application/json" not in accept:
        report_html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "report.html")
        if os.path.exists(report_html_path):
            return FileResponse(report_html_path)

    # API client fallback
    return get_report_json(report_token)


@app.post(
    "/report/{report_token}/revoke",
    summary="Revoke shareable verification report",
    description="Deactivates a shareable report so it can no longer be accessed.",
)
def revoke_share_report_endpoint(report_token: str, request: Optional[RevokeShareReportRequest] = None):
    """Permanently revokes a public report link."""
    clean_token = report_token.strip()
    revoke_token = request.revoke_token if request else None

    # Check existence
    status_result, _ = get_shareable_report(clean_token)
    if status_result == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification report not found or invalid token.",
        )

    success = revoke_shareable_report(clean_token, revoke_token=revoke_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Revocation failed. Invalid revocation credentials.",
        )

    return {
        "status": "success",
        "message": "Verification report has been permanently revoked.",
        "report_token": clean_token,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
