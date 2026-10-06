"""Unit tests for Dynamic Safety Recommendations Engine.

Tests:
1. Microsoft India fake internship scenario (HIGH risk, multiple triggered signals).
2. Medium risk scenario with specific signals.
3. Low risk genuine business scenario with standard due diligence advice.
4. FastAPI POST /check-company endpoint response includes safety_recommendations.
"""

import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.recommendations import generate_safety_recommendations
from app.utils.scoring import evaluate_rules


class TestSafetyRecommendations(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_microsoft_impersonation_recommendations(self):
        mca = {
            "company_name": "SOFT9 INDIA TECHNOLOGIES PVT LTD",
            "cin": "U72200DL2018PTC123456",
            "status": "Strike Off",
            "incorporation_date": "2018-03-15",
        }
        domain = {
            "domain": "microsoft-india-careers-apply.xyz",
            "ssl_status": "Unavailable",
            "has_ssl": False,
        }
        matching = {
            "claimed_name": "Microsoft India Careers & Technologies Pvt Ltd",
            "best_match": {"name": "SOFT9 INDIA TECHNOLOGIES PVT LTD"},
            "score": 71.0,
            "no_match": True,
        }
        job = {
            "company_name": "Microsoft India Careers & Technologies Pvt Ltd",
            "claimed_domain": "microsoft-india-careers-apply.xyz",
            "job_message": (
                "Congratulations! You have been selected for Microsoft India Careers. "
                "You must pay a mandatory registration fee of ₹1,999 within 24 hours. "
                "Immediate joining today! Please send your Aadhaar card and PAN card details "
                "along with your bank account number immediately to confirm your seat."
            ),
        }

        result = evaluate_rules(
            gst_result={},
            mca_result=mca,
            udyam_result={},
            domain_result=domain,
            matching_result=matching,
            job_details=job,
        )

        self.assertEqual(result["risk_level"], "HIGH")
        self.assertIn("safety_recommendations", result)
        recs = result["safety_recommendations"]
        self.assertIsInstance(recs, list)
        self.assertGreater(len(recs), 0)

        # 1. Upfront payment warning
        self.assertTrue(
            any("Do not pay registration, verification, training, placement, or internship fees" in r for r in recs)
        )

        # 2. Bank credentials / financial information warning
        self.assertTrue(
            any("Do not share bank credentials, OTPs, PINs, or payment information" in r for r in recs)
        )

        # 3. Sensitive identity documents warning
        self.assertTrue(
            any("Do not send sensitive identity documents" in r for r in recs)
        )

        # 4. Company name mismatch warning
        self.assertTrue(
            any("legal company name matches the organization offering the job" in r for r in recs)
        )

        # 5. Major company impersonation warning
        self.assertTrue(
            any("claims to represent a major company, contact that company through contact information obtained independently" in r for r in recs)
        )

        # 6. Lookalike domain warning
        self.assertTrue(
            any("Do not rely on links provided by the recruiter" in r for r in recs)
        )

        # 7. MCA Strike Off warning
        self.assertTrue(
            any("registered company identified by the verification system is inactive or struck off" in r for r in recs)
        )

        # 8. Urgency warning
        self.assertTrue(
            any("Do not make payments or share personal information because of time pressure" in r for r in recs)
        )

        # 9. High-risk independent contact recommendation
        self.assertTrue(
            any("Contact the company through independently obtained contact information" in r for r in recs)
        )

    def test_medium_risk_recommendations(self):
        triggered_rules = [
            {"rule": "company_name_mismatch", "score": 20},
            {"rule": "personal_email_contact", "score": 15},
        ]
        job = {
            "uses_personal_email": True,
            "company_name": "Apex Tech Solutions",
        }
        recs = generate_safety_recommendations(
            risk_level="MEDIUM",
            triggered_rules=triggered_rules,
            job_details=job,
            risk_score=35,
        )

        self.assertTrue(any("legal company name matches" in r for r in recs))
        self.assertTrue(any("personal email address" in r for r in recs))

    def test_low_risk_default_recommendations(self):
        recs = generate_safety_recommendations(
            risk_level="LOW",
            triggered_rules=[],
            job_details={"company_name": "Tata Consultancy Services Ltd"},
            risk_score=0,
        )

        self.assertIn("Verify the employer using its official website.", recs)
        self.assertIn("Confirm the recruiter's identity independently.", recs)
        self.assertIn("Do not pay unexpected recruitment or internship fees.", recs)

    def test_api_check_company_returns_safety_recommendations(self):
        payload = {
            "company_name": "Microsoft India Careers & Technologies Pvt Ltd",
            "claimed_domain": "microsoft-india-careers-apply.xyz",
            "job_message": "Pay registration fee of ₹999 within 24 hours. Send Aadhaar and bank account number.",
        }
        response = self.client.post("/check-company", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("safety_recommendations", data)
        self.assertIsInstance(data["safety_recommendations"], list)
        self.assertGreater(len(data["safety_recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
