# -*- coding: utf-8 -*-
"""Comprehensive automated test suite for:
1. Browser Extension Verification Endpoint (POST /extension/verify-job)
2. Dynamic Safety Recommendations Engine (app/utils/safety_recommendations.py)
3. Temporary Shareable Verification Reports & Sanitization (app/database.py & routes)
"""

import datetime
import os
import sqlite3
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.database import (
    init_db,
    create_shareable_report,
    get_shareable_report,
    revoke_shareable_report,
    sanitize_verification_data,
)
from app.utils.safety_recommendations import generate_safety_recommendations


class TestExtensionAndReports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_db_path = os.path.join(os.path.dirname(__file__), "data", "test_reports.db")
        init_db(cls.test_db_path)

    def tearDown(self):
        # Clean test db if exists
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    # =========================================================================
    # 1. BROWSER EXTENSION ENDPOINT TESTS
    # =========================================================================

    def test_extension_verify_job_success(self):
        payload = {
            "source": "linkedin",
            "company_name": "TCS Consultancy Services Pvt Ltd",
            "company_domain": "tcs.com",
            "job_title": "Senior Cloud Engineer",
            "job_description": "Join our cloud infrastructure team. Immediate requirement.",
            "recruiter_email": "recruiter@gmail.com",
            "visible_fee_info": None,
            "application_url": "https://www.linkedin.com/jobs/view/12345678"
        }
        response = self.client.post("/extension/verify-job", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("risk_score", data)
        self.assertIn("risk_level", data)
        self.assertIn("company_name", data)
        self.assertIn("verification_id", data)
        self.assertIn("warning_signals", data)
        self.assertIn("safety_recommendations", data)
        self.assertIn("full_report_url", data)
        self.assertTrue(data["verification_id"].startswith("VER-"))
        self.assertIsInstance(data["safety_recommendations"], list)
        self.assertGreater(len(data["safety_recommendations"]), 0)

    def test_extension_verify_job_with_fee_demand(self):
        payload = {
            "source": "generic",
            "company_name": "Infosys Career Portal Scam",
            "company_domain": "infosys-job-careers.xyz",
            "job_title": "Data Entry Specialist",
            "job_description": "Pay registration fee of ₹1500 to confirm interview seat. Send Aadhaar card and bank account.",
            "visible_fee_info": "Registration fee ₹1500",
            "recruiter_email": "hr@gmail.com"
        }
        response = self.client.post("/extension/verify-job", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["risk_level"], "HIGH")
        self.assertGreater(data["risk_score"], 50)
        
        # Verify payment recommendation triggered
        rec_types = [r["type"] for r in data["safety_recommendations"] if isinstance(r, dict)]
        self.assertIn("payment", rec_types)

    def test_extension_verify_job_validation_error(self):
        # Missing company name
        response = self.client.post("/extension/verify-job", json={"company_name": ""})
        self.assertEqual(response.status_code, 422)

    # =========================================================================
    # 2. DYNAMIC SAFETY RECOMMENDATIONS SCENARIO TESTS
    # =========================================================================

    def test_recommendation_payment_detected(self):
        res = {
            "risk_level": "HIGH",
            "reasons": ["Upfront payment requested before employment/internship."],
            "triggered_rules": [{"rule": "upfront_payment_demanded", "weight": 35, "reason": "Registration fee"}],
            "job_details": {"job_message": "Please pay 999 INR refundable security deposit."}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("payment", types)
        pay_rec = next(r for r in recs if r["type"] == "payment")
        self.assertIn("Do not pay", pay_rec["message"])
        self.assertEqual(pay_rec["priority"], "high")

    def test_recommendation_sensitive_info_detected(self):
        res = {
            "risk_level": "HIGH",
            "reasons": ["Sensitive personal or financial information requested before verification."],
            "triggered_rules": [{"rule": "sensitive_documents_requested", "weight": 15, "reason": "Aadhaar and bank account"}],
            "job_details": {"job_message": "Submit your Aadhaar, PAN card, and bank account details."}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("sensitive_info", types)
        info_rec = next(r for r in recs if r["type"] == "sensitive_info")
        self.assertIn("Aadhaar", info_rec["message"])
        self.assertEqual(info_rec["priority"], "high")

    def test_recommendation_company_mismatch(self):
        res = {
            "risk_level": "HIGH",
            "reasons": ["Company name discrepancy across sources."],
            "triggered_rules": [{"rule": "company_name_mismatch", "weight": 20, "reason": "Discrepancy"}],
            "company_match": {"claimed_name": "Google India", "best_match": {"name": "G00GLE TECH PRIVATE LIMITED"}}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("company_mismatch", types)
        rec = next(r for r in recs if r["type"] == "company_mismatch")
        self.assertIn("discrepancy", rec["message"].lower())

    def test_recommendation_impersonation(self):
        res = {
            "risk_level": "HIGH",
            "reasons": ["Possible major-company impersonation."],
            "triggered_rules": [{"rule": "major_company_impersonation", "weight": 25, "reason": "Impersonation"}],
            "company_match": {"claimed_name": "Microsoft India Careers"}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("impersonation", types)
        rec = next(r for r in recs if r["type"] == "impersonation")
        self.assertIn("impersonate", rec["message"].lower())

    def test_recommendation_suspicious_domain(self):
        res = {
            "risk_level": "HIGH",
            "reasons": ["Suspicious lookalike domain."],
            "triggered_rules": [{"rule": "suspicious_lookalike_domain", "weight": 20, "reason": "Lookalike"}],
            "domain": {"domain": "tcs-hiring-portal.xyz", "ssl_status": "unavailable"}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("suspicious_domain", types)

    def test_recommendation_urgency(self):
        res = {
            "risk_level": "MEDIUM",
            "reasons": ["Urgency or pressure tactics detected in the job communication."],
            "triggered_rules": [{"rule": "urgency_pressure_tactics", "weight": 10, "reason": "Urgency"}],
            "job_details": {"job_message": "Offer expires in 2 hours! Immediate response mandatory."}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("urgency", types)

    def test_recommendation_personal_email(self):
        res = {
            "risk_level": "MEDIUM",
            "reasons": ["Personal / free email used for corporate recruitment."],
            "triggered_rules": [{"rule": "personal_email_contact", "weight": 15, "reason": "Gmail used"}],
            "job_details": {"notes": "Contact recruiter at hr.tcs.jobs@gmail.com"}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("personal_email", types)

    def test_recommendation_mca_struck_off(self):
        res = {
            "risk_level": "HIGH",
            "reasons": ["MCA entity is inactive or struck off."],
            "triggered_rules": [{"rule": "mca_struck_off", "weight": 25, "reason": "Struck Off"}],
            "mca": {"status": "Strike Off", "company_name": "XYZ Corp Pvt Ltd"}
        }
        recs = generate_safety_recommendations(res)
        types = [r["type"] for r in recs]
        self.assertIn("mca_status", types)
        rec = next(r for r in recs if r["type"] == "mca_status")
        self.assertIn("inactive or struck off", rec["message"].lower())

    def test_recommendation_low_risk_neutral_guidance(self):
        # Must provide safe guidance and NEVER say "100% Safe"
        res = {
            "risk_level": "LOW",
            "risk_score": 0,
            "reasons": [],
            "triggered_rules": [],
            "mca": {"status": "Active", "company_name": "Infosys Limited"},
            "gst": {"status": "Active"},
            "domain": {"status": "Verified", "ssl_status": "Valid"}
        }
        recs = generate_safety_recommendations(res)
        self.assertGreater(len(recs), 0)
        for r in recs:
            msg = r.get("message", "")
            self.assertNotIn("100% safe", msg.lower())
            self.assertNotIn("guaranteed legitimate", msg.lower())

    # =========================================================================
    # 3. TEMPORARY SHAREABLE VERIFICATION REPORT TESTS
    # =========================================================================

    def test_create_and_access_shareable_report(self):
        # Create share report
        report_payload = {
            "verification_id": "VER-2026-99001",
            "report_data": {
                "company_name": "Tata Consultancy Services Limited",
                "risk_score": 5,
                "risk_level": "LOW",
                "verified_at": "22 September 2026, 04:00 PM",
                "mca": {"status": "Active", "company_name": "Tata Consultancy Services Limited", "cin": "L22210MH1995PLC084781"},
                "gst": {"status": "Active", "gstin": "27AAACT2727Q1ZW", "legal_name": "Tata Consultancy Services Limited"},
                "domain": {"domain": "tcs.com", "status": "Verified", "ssl_status": "Valid"},
                "safety_recommendations": [{"type": "general", "title": "Verified entity", "message": "Standard due diligence advised.", "priority": "low"}],
                # Private data that MUST be stripped:
                "aadhaar_number": "1234-5678-9012",
                "bank_account": "98765432109876",
                "raw_upload_file": "sensitive_offer_letter.pdf",
                "recruiter_private_phone": "9999999999"
            }
        }

        resp = self.client.post("/create-share-report", json=report_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        token = data["report_token"]
        revoke_token = data["revoke_token"]
        expires_at = data["expires_at"]
        self.assertTrue(len(token) > 20)
        self.assertTrue(len(revoke_token) > 20)
        self.assertIn("share_url", data)

        # Access via JSON endpoint
        get_resp = self.client.get(f"/api/report/{token}")
        self.assertEqual(get_resp.status_code, 200)
        report_data = get_resp.json()

        # Check public allowed data is present
        self.assertEqual(report_data["company_name"], "Tata Consultancy Services Limited")
        self.assertEqual(report_data["risk_level"], "LOW")
        self.assertEqual(report_data["verification_id"], "VER-2026-99001")
        self.assertIn("mca", report_data)
        self.assertIn("gst", report_data)

        # Check sensitive data is strictly stripped
        self.assertNotIn("aadhaar_number", report_data)
        self.assertNotIn("bank_account", report_data)
        self.assertNotIn("raw_upload_file", report_data)
        self.assertNotIn("recruiter_private_phone", report_data)

        # Access via HTML content negotiation
        html_resp = self.client.get(f"/report/{token}", headers={"Accept": "text/html"})
        self.assertEqual(html_resp.status_code, 200)
        self.assertIn("text/html", html_resp.headers.get("content-type", ""))

        # Revoke the report
        rev_resp = self.client.post(f"/report/{token}/revoke", json={"revoke_token": revoke_token})
        self.assertEqual(rev_resp.status_code, 200)

        # Subsequent access must return 410 Gone
        revoked_resp = self.client.get(f"/api/report/{token}")
        self.assertEqual(revoked_resp.status_code, 410)

    def test_report_not_found(self):
        resp = self.client.get("/api/report/non_existent_token_123456789")
        self.assertEqual(resp.status_code, 404)

    def test_report_expiration(self):
        # Insert a report already expired into the database directly
        db_path = os.path.join(os.path.dirname(__file__), "data", "reports.db")
        conn = sqlite3.connect(db_path)
        past_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
        token = "expired_token_test_12345"
        conn.execute(
            """
            INSERT OR REPLACE INTO verification_reports (
                verification_id, report_token, revoke_token, sanitized_report_data, created_at, expires_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            ("VER-TEST-EXP", token, "rev_tok", "{}", past_date, past_date)
        )
        conn.commit()
        conn.close()

        resp = self.client.get(f"/api/report/{token}")
        self.assertEqual(resp.status_code, 410)
        self.assertIn("expired", resp.json()["detail"].lower())

    def test_recheck_preserves_verification_id(self):
        # Initial check
        chk_resp = self.client.post("/check-company", json={"company_name": "Wipro Limited"})
        self.assertEqual(chk_resp.status_code, 200)
        initial_data = chk_resp.json()
        initial_ver_id = initial_data.get("verification_id")
        self.assertIsNotNone(initial_ver_id)
        self.assertTrue(initial_ver_id.startswith("VER-"))

        # Recheck with previous_result
        recheck_resp = self.client.post(
            "/recheck-company",
            json={
                "company_name": "Wipro Limited",
                "previous_result": initial_data,
            }
        )
        self.assertEqual(recheck_resp.status_code, 200)
        recheck_data = recheck_resp.json()
        self.assertEqual(recheck_data["verification_id"], initial_ver_id)


if __name__ == "__main__":
    unittest.main()