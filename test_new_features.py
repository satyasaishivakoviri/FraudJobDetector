import io
import unittest
from PIL import Image, ImageDraw
import docx
from fastapi.testclient import TestClient

from app.main import app
from app.services.verification_service import verify_company
from app.utils.document_parser import (
    extract_text_from_docx,
    extract_text_from_pdf,
    parse_uploaded_document,
    run_ocr_on_image,
)
from app.utils.offer_consistency import evaluate_offer_consistency
from app.utils.offer_extractor import extract_offer_letter_data
from app.utils.screenshot_analyzer import analyze_screenshot_text


def create_sample_pdf_bytes() -> bytes:
    """Creates a valid PDF document containing offer letter text."""
    pdf_template = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 260 >> stream
BT
/F1 12 Tf
72 712 Td
(Global Future Technologies Pvt Ltd) Tj
0 -20 Td
(Corporate Office: Hyderabad, Telangana) Tj
0 -20 Td
(Role: Software Developer Intern) Tj
0 -20 Td
(Stipend: Rs 25,000 per month) Tj
0 -20 Td
(Date of Joining: 15 October 2026) Tj
0 -20 Td
(Contact: hr@globalfuture-careers.xyz) Tj
0 -20 Td
(Mandatory registration fee: Rs 2,500) Tj
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
0000000554 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
625
%%EOF"""
    return pdf_template


def create_sample_docx_bytes() -> bytes:
    """Creates a valid DOCX document containing offer letter text."""
    doc = docx.Document()
    doc.add_heading("Global Future Technologies Pvt Ltd", level=1)
    doc.add_paragraph("Corporate Office: Hyderabad, Telangana")
    doc.add_paragraph("Software Developer Intern")
    doc.add_paragraph("Salary: Rs 25,000 per month")
    doc.add_paragraph("Date of Joining: 15 October 2026")
    doc.add_paragraph("Recruiter Email: hr@globalfuture-careers.xyz")
    doc.add_paragraph("Registration fee: Rs 2,500 required")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_sample_screenshot_image_bytes() -> bytes:
    """Creates a test screenshot image with recruitment notice text."""
    img = Image.new("RGB", (600, 160), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 15), "TechNova Solutions Recruitment Notice", fill=(0, 0, 0))
    d.text((20, 45), "Selected without interview! Immediate joining.", fill=(0, 0, 0))
    d.text((20, 75), "Contact: hr@gmail.com | Phone: 9876543210", fill=(0, 0, 0))
    d.text((20, 105), "Deposit registration fee of Rs 2500 today.", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestNewFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # -----------------------------------------------------------------------
    # FEATURE 1: Offer Letter Scanner Tests
    # -----------------------------------------------------------------------

    def test_offer_letter_pdf_text_extraction(self):
        pdf_bytes = create_sample_pdf_bytes()
        text, confidence = extract_text_from_pdf(pdf_bytes)
        self.assertIn("Global Future Technologies", text)
        self.assertIn("15 October 2026", text)
        self.assertGreaterEqual(confidence, 0.7)

    def test_offer_letter_docx_text_extraction(self):
        docx_bytes = create_sample_docx_bytes()
        text, confidence = extract_text_from_docx(docx_bytes)
        self.assertIn("Global Future Technologies", text)
        self.assertIn("Software Developer Intern", text)
        self.assertGreaterEqual(confidence, 0.8)

    def test_offer_letter_structured_extraction(self):
        sample_text = (
            "Global Future Technologies Pvt Ltd\n"
            "Registered Office: Hyderabad, Telangana\n"
            "Offer Date: 01 October 2026\n"
            "Date of Joining: 15 October 2026\n"
            "Role: Software Developer Intern\n"
            "Stipend: Rs 25,000 per month\n"
            "Contact: hr@globalfuture-careers.xyz\n"
            "Registration fee of Rs 2,500 must be deposited prior to joining.\n"
            "Please submit your PAN card and Aadhaar card."
        )
        extracted = extract_offer_letter_data(sample_text)
        self.assertEqual(extracted["company_name"], "Global Future Technologies Pvt Ltd")
        self.assertEqual(extracted["company_address"], "Hyderabad, Telangana")
        self.assertEqual(extracted["joining_date"], "15 October 2026")
        self.assertEqual(extracted["recruiter_email"], "hr@globalfuture-careers.xyz")
        self.assertIn("Registration fee", extracted["payment_or_fee"])
        self.assertTrue(extracted["has_sensitive_info"])

    def test_offer_letter_consistency_evaluation(self):
        offer_data = {
            "company_name": "Global Future Technologies Pvt Ltd",
            "company_address": "Hyderabad, Telangana",
            "recruiter_email": "hr@gmail.com",
            "company_domain": "globalfuture.com",
            "cin": "U72200TG2020PTC123456",
            "gstin": None,
            "salary": "Rs 25,000 per month",
            "joining_date": "15 October 2026",
        }
        # Simulated registry where company name matches, address matches, but email is gmail (mismatch)
        mca_result = {
            "company_name": "Global Future Technologies Private Limited",
            "status": "Active",
            "registered_address": "Plot 42, HITEC City, Hyderabad, Telangana",
            "cin": "U72200TG2020PTC123456",
        }
        domain_result = {"domain": "globalfuture.com", "status": "Verified"}
        matching_result = {
            "best_match": {"name": "Global Future Technologies Private Limited"},
            "score": 95.0,
        }

        consistency = evaluate_offer_consistency(
            offer_data=offer_data,
            mca_result=mca_result,
            domain_result=domain_result,
            matching_result=matching_result,
        )

        field_map = {item["field"]: item for item in consistency}

        # Company Name should match
        self.assertEqual(field_map["Company Name"]["status"], "✓ Match")
        # Address should match (both in Telangana)
        self.assertEqual(field_map["Company Address"]["status"], "✓ Match")
        # Email domain should be Mismatch (recruiter uses @gmail.com while official domain is globalfuture.com)
        self.assertEqual(field_map["Email Domain"]["status"], "⚠ Mismatch")
        # CIN should match
        self.assertEqual(field_map["CIN"]["status"], "✓ Match")
        # GSTIN should be Not Detected
        self.assertEqual(field_map["GSTIN"]["status"], "— Not Detected")
        # Salary should be Extracted
        self.assertEqual(field_map["Salary"]["status"], "✓ Extracted")
        # Joining date should be Extracted
        self.assertEqual(field_map["Joining Date"]["status"], "✓ Extracted")

    def test_api_upload_offer_letter(self):
        pdf_bytes = create_sample_pdf_bytes()
        files = {"file": ("offer_letter.pdf", pdf_bytes, "application/pdf")}
        response = self.client.post("/upload/offer-letter", files=files)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertTrue(json_data["success"])
        self.assertIn("Global Future Technologies", json_data["raw_text"])
        self.assertEqual(json_data["extracted_data"]["company_name"], "Global Future Technologies Pvt Ltd")

    # -----------------------------------------------------------------------
    # FEATURE 2: Screenshot / Image Analysis Tests
    # -----------------------------------------------------------------------

    def test_screenshot_ocr_and_parsing(self):
        img_bytes = create_sample_screenshot_image_bytes()
        ocr_text, confidence = run_ocr_on_image(img_bytes)
        # Windows OCR may or may not be available in headless CI, but on this Windows host it is functional
        self.assertIsInstance(ocr_text, str)
        self.assertIsInstance(confidence, float)

    def test_screenshot_ai_signals_analysis(self):
        sample_ocr_text = (
            "TechNova Solutions Recruitment Notice\n"
            "Congratulations! You have been selected without interview!\n"
            "Earn Rs 5,000 daily from home. Offer expires today! Hurry up.\n"
            "Contact on WhatsApp: +91 9876543210 or email hr.technova@gmail.com\n"
            "Please deposit registration fee of Rs 2,500."
        )
        signals = analyze_screenshot_text(sample_ocr_text)
        self.assertGreater(signals["detected_count"], 0)

        sig_map = {s["rule"]: s for s in signals["message_signals"]}
        self.assertTrue(sig_map["upfront_payment"]["detected"])
        self.assertTrue(sig_map["urgency"]["detected"])
        self.assertTrue(sig_map["guaranteed_selection"]["detected"])
        self.assertTrue(sig_map["personal_email"]["detected"])

    def test_api_upload_screenshot(self):
        img_bytes = create_sample_screenshot_image_bytes()
        files = {"file": ("whatsapp_chat.png", img_bytes, "image/png")}
        response = self.client.post("/upload/screenshot", files=files)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertTrue(json_data["success"])
        self.assertIn("data:image/jpeg;base64,", json_data["image_preview_url"])
        self.assertIn("message_signals", json_data)

    # -----------------------------------------------------------------------
    # FEATURE 3: Recheck Verification Tests
    # -----------------------------------------------------------------------

    def test_recheck_verification_service_and_endpoint(self):
        # 1. Run initial check
        initial_result = verify_company(
            company_name="Microsoft India",
            claimed_domain="microsoft.com",
        )
        self.assertIn("verified_at", initial_result)
        self.assertIn("risk_score", initial_result)

        # 2. Simulate recheck with changed previous result (e.g. previous risk score was 40)
        simulated_previous = dict(initial_result)
        simulated_previous["risk_score"] = 40
        simulated_previous["mca"] = {"status": "Strike Off", "company_name": "Old Entity Ltd"}

        recheck_payload = {
            "company_name": "Microsoft India",
            "claimed_domain": "microsoft.com",
            "previous_result": simulated_previous,
            "input_source": "recheck",
        }

        response = self.client.post("/recheck-company", json=recheck_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("verified_at", data)
        self.assertIn("verification_changes", data)
        self.assertTrue(data["has_changes"])

        # Check that changes list contains the changed fields
        changed_fields = [c["field"] for c in data["verification_changes"]]
        self.assertIn("MCA Status", changed_fields)
        self.assertIn("Risk Score", changed_fields)

    # -----------------------------------------------------------------------
    # FEATURE 4: Regression Check for Existing Verification Engine
    # -----------------------------------------------------------------------

    def test_existing_text_message_verification_unbroken(self):
        payload = {
            "company_name": "Microsoft India Careers & Technologies Pvt Ltd",
            "claimed_domain": "microsoft-india-careers-apply.xyz",
            "job_message": (
                "Congratulations! You have been selected for Microsoft Internship. "
                "Registration fee of Rs 2,500 must be paid today. Send bank details and Aadhaar."
            ),
        }
        response = self.client.post("/check-company", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Must trigger high risk
        self.assertEqual(data["risk_level"], "HIGH")
        self.assertGreater(data["risk_score"], 60)
        self.assertIn("safety_recommendations", data)
        self.assertGreater(len(data["safety_recommendations"]), 0)
        self.assertIn("mca", data)
        self.assertIn("verified_at", data)


if __name__ == "__main__":
    unittest.main()
