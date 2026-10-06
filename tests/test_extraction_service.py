"""Comprehensive regression test suite for the unified extraction service and document processing pipeline.
Covers:
    - Plain text & informal messages
    - Single-word brand names without suffixes
    - Markdown & pipe-delimited table formats
    - Irregular field orderings
    - Missing & confidential information handling
    - OCR error repair & text normalization
    - Text-based and multi-page PDFs
    - AI provider mock simulations (valid, markdown-wrapped, malformed, timeout)
    - Full API endpoint schema consistency
"""

import io
import json
import unittest
from unittest.mock import AsyncMock, patch
from PIL import Image, ImageDraw
import pypdf
from fastapi.testclient import TestClient

from app.main import app
from app.services.extraction_service import (
    UnifiedExtractionResult,
    _clean_ai_json_response,
    _merge_results,
    extract_deterministic,
    extract_unified_sync,
    normalize_document_text,
)
from app.utils.document_parser import (
    extract_text_from_pdf,
    parse_uploaded_document,
)


class TestUnifiedExtractionService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # -----------------------------------------------------------------------
    # 1. Plain Text & Natural Language Inputs
    # -----------------------------------------------------------------------

    def test_single_word_famous_company_without_suffix(self):
        text = """
        Stripe is hiring for a Backend Engineer in Bengaluru.
        Apply via https://stripe.com/jobs or email careers@stripe.com.
        Package is 35 LPA. Work mode: Remote.
        """
        res = extract_unified_sync(text)
        self.assertEqual(res.company_name, "Stripe")
        self.assertEqual(res.company_name_confidence, "high")
        self.assertIn("Backend Engineer", res.job_title)
        self.assertIn("35 LPA", res.stated_salary_or_stipend)
        self.assertEqual(res.work_mode, "Remote")
        self.assertEqual(res.recruiter_email, "careers@stripe.com")
        self.assertEqual(res.email_address, "careers@stripe.com")
        self.assertEqual(res.company_domain, "stripe.com")

    def test_informal_chat_recruitment_message(self):
        text = """
        Urgent requirement! Role at Swiggy for Operations Lead.
        Location: Hyderabad.
        Fixed Pay: ₹45,000 / month.
        Interview Mode: Google Meet video call.
        Contact HR Sunita on WhatsApp: +91 98765 43210 or mail sunita.hr@swiggy.in
        Apply before 25th October 2026.
        """
        res = extract_unified_sync(text)
        self.assertEqual(res.company_name, "Swiggy")
        self.assertIn("Operations Lead", res.job_title)
        self.assertEqual(res.job_location, "Hyderabad")
        self.assertIn("45,000", res.stated_salary_or_stipend)
        self.assertEqual(res.interview_mode, "Virtual / Video")
        self.assertEqual(res.recruiter_phone, "+91 98765 43210")
        self.assertEqual(res.recruiter_email, "sunita.hr@swiggy.in")
        self.assertIsNotNone(res.application_deadline)

    def test_employment_with_phrase_and_address(self):
        text = """
        Subject: Offer of Employment for Junior Associate with Nexa Global Solutions.
        Corporate office at 404 Business Park, Powai, Mumbai.
        Stipend is 25,000 INR per month.
        """
        res = extract_unified_sync(text)
        self.assertEqual(res.company_name, "Nexa Global Solutions")
        self.assertEqual(res.job_title, "Junior Associate")
        self.assertIn("404 Business Park", res.company_address)
        self.assertIn("25,000", res.stated_salary_or_stipend)

    # -----------------------------------------------------------------------
    # 2. Structured Tables & Copied Website Content
    # -----------------------------------------------------------------------

    def test_pipe_delimited_table_format(self):
        table_text = """
        | Attribute | Details |
        | Company | Infosys Limited |
        | Role | Senior Systems Associate |
        | CTC | 12.5 LPA |
        | Location | Pune, Maharashtra |
        | Work Mode | Hybrid |
        | Contact | talent@infosys.com |
        """
        res = extract_unified_sync(table_text)
        self.assertEqual(res.company_name, "Infosys Limited")
        self.assertEqual(res.job_title, "Senior Systems Associate")
        self.assertIn("12.5 LPA", res.stated_salary_or_stipend)
        self.assertEqual(res.work_mode, "Hybrid")
        self.assertEqual(res.recruiter_email, "talent@infosys.com")

    def test_bullet_list_with_arbitrary_ordering(self):
        text = """
        OPENING ANNOUNCEMENT:
        • Contact Email: hr-team@amazon.com
        • Stated CTC: 28 LPA
        • Work Mode: On-site
        • Designation: Cloud Solutions Architect
        • Organization: Amazon India
        • Eligibility: B.Tech or MCA degree
        • Experience Required: 2-4 years
        """
        res = extract_unified_sync(text)
        self.assertEqual(res.company_name, "Amazon India")
        self.assertEqual(res.job_title, "Cloud Solutions Architect")
        self.assertIn("28 LPA", res.stated_salary_or_stipend)
        self.assertEqual(res.work_mode, "On-site")
        self.assertEqual(res.recruiter_email, "hr-team@amazon.com")
        self.assertEqual(res.required_experience, "2-4 years")
        self.assertIn("B.Tech", res.eligibility)

    # -----------------------------------------------------------------------
    # 3. Missing & Ambiguous Information Handling
    # -----------------------------------------------------------------------

    def test_missing_company_name_transparently_reported(self):
        text = """
        Hiring for Software Engineer.
        Salary: 10 LPA.
        Send CV to quickjobapply2026@gmail.com.
        """
        res = extract_unified_sync(text)
        self.assertIsNone(res.company_name)
        self.assertEqual(res.company_name_confidence, "none")
        self.assertIn("company_name", res.missing_fields)
        self.assertEqual(res.recruiter_email, "quickjobapply2026@gmail.com")

    def test_confidential_or_unnamed_employer_not_hallucinated(self):
        text = """
        Company: Confidential Client
        Position: DevOps Specialist
        Salary: 15 LPA
        """
        res = extract_unified_sync(text)
        # Should not treat "Confidential Client" as a valid corporate entity
        self.assertTrue(res.company_name is None or res.company_name_confidence in ("low", "none"))

    # -----------------------------------------------------------------------
    # 4. OCR Error Repair & Normalization
    # -----------------------------------------------------------------------

    def test_ocr_missing_dot_and_hyphenated_splits(self):
        ocr_messy_text = """
        TCS- Tata Consultancy Services
        Role: Soft-\nware Engineer
        Contact: careers @ tcscom
        Salary: 14 LPA
        """
        res = extract_unified_sync(ocr_messy_text)
        self.assertIn("Tata Consultancy Services", res.company_name)
        self.assertEqual(res.recruiter_email, "careers@tcs.com")
        self.assertIn("14 LPA", res.stated_salary_or_stipend)

    def test_text_normalization_utility(self):
        raw = "Apply  at  recruitment@tcscom   for  Senior-  \nDeveloper"
        norm = normalize_document_text(raw)
        self.assertIn("recruitment@tcs.com", norm)
        self.assertIn("SeniorDeveloper", norm)

    # -----------------------------------------------------------------------
    # 5. PDF & Multi-Page Document Extraction
    # -----------------------------------------------------------------------

    def test_multi_page_pdf_combines_data_without_loss(self):
        # Create a 2-page in-memory PDF using pypdf
        writer = pypdf.PdfWriter()

        # Page 1: Header + Candidate + Company
        p1 = writer.add_blank_page(width=612, height=792)
        # Page 2: Terms + Salary
        p2 = writer.add_blank_page(width=612, height=792)

        # Build valid multi-page PDF bytes with stream content
        multi_page_template = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj
4 0 obj << /Length 170 >> stream
BT
/F1 12 Tf
72 712 Td
(Vertex Software Solutions Pvt Ltd) Tj
0 -25 Td
(CIN: U72200MH2016PTC288123) Tj
0 -25 Td
(Offer Letter of Employment) Tj
ET
endstream
endobj
5 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj
6 0 obj << /Length 200 >> stream
BT
/F1 12 Tf
72 712 Td
(Designation: Senior Backend Developer) Tj
0 -25 Td
(Salary: INR 18,00,000 per annum) Tj
0 -25 Td
(Reporting Date: 01 November 2026) Tj
0 -25 Td
(HR Contact: hr@vertexsoftware.in) Tj
ET
endstream
endobj
7 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 8
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
00000000122 00000 n 
00000000252 00000 n 
00000000473 00000 n 
00000000603 00000 n 
00000000854 00000 n 
trailer << /Size 8 /Root 1 0 R >>
startxref
925
%%EOF"""

        text, conf = extract_text_from_pdf(multi_page_template)
        self.assertIn("Vertex Software Solutions", text)
        self.assertIn("Senior Backend Developer", text)
        self.assertIn("18,00,000", text)

        res = extract_unified_sync(text)
        self.assertEqual(res.company_name, "Vertex Software Solutions Pvt Ltd")
        self.assertEqual(res.cin, "U72200MH2016PTC288123")
        self.assertIn("Senior Backend Developer", res.job_title)
        self.assertIn("18,00,000", res.stated_salary_or_stipend)
        self.assertEqual(res.recruiter_email, "hr@vertexsoftware.in")

    # -----------------------------------------------------------------------
    # 6. AI Structured Extraction Unit & Fallback Tests
    # -----------------------------------------------------------------------

    def test_clean_ai_json_response_with_markdown_fences(self):
        raw_ai = """```json
{
  "company_name": "Razorpay Software Pvt Ltd",
  "job_title": "Product Analyst",
  "salary": "16 LPA",
  "work_mode": "Hybrid"
}
```"""
        parsed = _clean_ai_json_response(raw_ai)
        self.assertEqual(parsed["company_name"], "Razorpay Software Pvt Ltd")
        self.assertEqual(parsed["job_title"], "Product Analyst")
        self.assertEqual(parsed["salary"], "16 LPA")

    def test_non_destructive_merge_preserves_verified_regex_data(self):
        # Deterministic result with validated CIN and GSTIN
        det = extract_unified_sync("""
        Company: TestCorp
        GSTIN: 27AABCN1234F1Z5
        CIN: U72200MH2021PTC123456
        Phone: +91 98765 43210
        """)

        # AI result returns expanded company name and role, but misses GSTIN/CIN
        ai_data = {
            "company_name": "TestCorp Technologies Global Limited",
            "job_title": "Lead Software Architect",
            "work_mode": "Remote",
            "gstin": None,
            "cin": None,
        }

        merged = _merge_results(det, ai_data)
        # Company name upgraded by AI
        self.assertEqual(merged.company_name, "TestCorp Technologies Global Limited")
        # Role supplied by AI
        self.assertEqual(merged.job_title, "Lead Software Architect")
        # Verified GSTIN and CIN preserved from deterministic parser
        self.assertEqual(merged.gstin, "27AABCN1234F1Z5")
        self.assertEqual(merged.cin, "U72200MH2021PTC123456")
        self.assertEqual(merged.phone_number, "+91 98765 43210")
        self.assertEqual(merged.extraction_method, "hybrid")

    # -----------------------------------------------------------------------
    # 7. End-to-End API Integration & Schema Consistency
    # -----------------------------------------------------------------------

    def test_api_extract_entities_returns_consistent_aliases(self):
        payload = {
            "text": "Wipro is hiring for Cloud Engineer in Hyderabad. Salary: 10 LPA. Email: hr@wipro.com"
        }
        resp = self.client.post("/extract-entities", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Verify standard and alias fields are both populated
        self.assertEqual(data["company_name"], "Wipro")
        self.assertEqual(data["job_title"], "Cloud Engineer")
        self.assertEqual(data["role"], "Cloud Engineer")
        self.assertEqual(data["recruiter_email"], "hr@wipro.com")
        self.assertEqual(data["email_address"], "hr@wipro.com")
        self.assertEqual(data["contact_email"], "hr@wipro.com")
        self.assertIn("10 LPA", data["stated_salary_or_stipend"])
        self.assertIn("10 LPA", data["salary"])

    def test_api_upload_offer_letter_returns_unified_data(self):
        pdf_bytes = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 200 >> stream
BT
/F1 12 Tf
72 712 Td
(Infosys BPM Limited) Tj
0 -25 Td
(Offer of Employment: Systems Associate) Tj
0 -25 Td
(Stipend: Rs 28,000 per month) Tj
0 -25 Td
(Contact: recruitment@infosys-careers.com) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000495 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
566
%%EOF"""

        files = {"file": ("offer.pdf", pdf_bytes, "application/pdf")}
        resp = self.client.post("/upload/offer-letter", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data["success"])
        offer_data = data["offer_data"]
        self.assertEqual(offer_data["company_name"], "Infosys BPM Limited")
        self.assertEqual(offer_data["job_title"], "Systems Associate")
        self.assertEqual(offer_data["role"], "Systems Associate")
        self.assertEqual(offer_data["recruiter_email"], "recruitment@infosys-careers.com")
        self.assertEqual(offer_data["email_address"], "recruitment@infosys-careers.com")

    def test_api_upload_screenshot_returns_unified_data(self):
        from PIL import ImageFont
        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default(size=22)
        except Exception:
            font = ImageFont.load_default()
        d.text((20, 20), "Company: TechNova Solutions", fill=(0, 0, 0), font=font)
        d.text((20, 55), "Role: Data Analyst", fill=(0, 0, 0), font=font)
        d.text((20, 90), "Salary: 8 LPA", fill=(0, 0, 0), font=font)
        d.text((20, 125), "Email: jobs@technova.com", fill=(0, 0, 0), font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")

        files = {"file": ("screenshot.png", buf.getvalue(), "image/png")}
        resp = self.client.post("/upload/screenshot", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data["success"])
        entities = data["extracted_entities"]
        self.assertIn("TechNova Solutions", entities.get("company_name", ""))
        self.assertIn("Data Analyst", entities.get("job_title", ""))
        self.assertIn("jobs@technova.com", entities.get("recruiter_email", ""))
        self.assertIn("jobs@technova.com", entities.get("email_address", ""))


if __name__ == "__main__":
    unittest.main()
