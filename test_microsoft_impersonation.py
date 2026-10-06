"""Test script for the Microsoft Impersonation scenario.

Verifies:
- MCA Strike Off (+25)
- Company Name Mismatch (+20)
- Possible Major Company Impersonation (+25)
- Suspicious Lookalike Domain (+20)
- Suspicious TLD (+15)
- SSL Unavailable (+10)
- Upfront Payment (+35)
- Urgency (+10)
- Sensitive Documents (+15)
- Total Score ~ 175
- Risk Level: HIGH
"""

import unittest
from app.utils.scoring import evaluate_rules


class TestMicrosoftImpersonation(unittest.TestCase):
    def test_microsoft_india_impersonation_case(self):
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

        triggered_rule_names = {r["rule"] for r in result["triggered_rules"]}
        print("\n--- Triggered Rules for Microsoft Scenario ---")
        for r in result["triggered_rules"]:
            print(f"[{r['rule']}] +{r['score']} — {r['reason']}")
        print("-----------------------------------------------")
        print(f"Total Risk Score: {result['risk_score']}")
        print(f"Final Risk Level: {result['risk_level']}")

        # 1. Check individual expected rules
        self.assertIn("mca_struck_off", triggered_rule_names)
        self.assertIn("company_name_mismatch", triggered_rule_names)
        self.assertIn("major_company_impersonation", triggered_rule_names)
        self.assertIn("suspicious_lookalike_domain", triggered_rule_names)
        self.assertIn("suspicious_or_free_tld", triggered_rule_names)
        self.assertIn("ssl_unavailable_or_invalid", triggered_rule_names)
        self.assertIn("upfront_payment_demanded", triggered_rule_names)
        self.assertIn("urgency_pressure_tactics", triggered_rule_names)
        self.assertIn("sensitive_documents_requested", triggered_rule_names)

        # 2. Check rule weights
        rule_scores = {r["rule"]: r["score"] for r in result["triggered_rules"]}
        self.assertEqual(rule_scores["mca_struck_off"], 25)
        self.assertEqual(rule_scores["company_name_mismatch"], 20)
        self.assertEqual(rule_scores["major_company_impersonation"], 25)
        self.assertEqual(rule_scores["suspicious_lookalike_domain"], 20)
        self.assertEqual(rule_scores["suspicious_or_free_tld"], 15)
        self.assertEqual(rule_scores["ssl_unavailable_or_invalid"], 10)
        self.assertEqual(rule_scores["upfront_payment_demanded"], 35)
        self.assertEqual(rule_scores["urgency_pressure_tactics"], 10)
        self.assertEqual(rule_scores["sensitive_documents_requested"], 15)

        # 3. Check calculated cumulative score
        expected_score = 25 + 20 + 25 + 20 + 15 + 10 + 35 + 10 + 15  # 175
        self.assertEqual(result["risk_score"], expected_score)

        # 4. Check risk level
        self.assertEqual(result["risk_level"], "HIGH")

    def test_critical_risk_override_low_score(self):
        """Test critical risk override promotes to HIGH when score < 51."""
        # MCA struck off (+25) + Name mismatch (+20) = 45 (< 51), but must be HIGH!
        mca = {"status": "Strike Off", "cin": "U12345"}
        matching = {"score": 40.0, "best_match": {"name": "DIFFERENT ENTITY"}, "no_match": True}
        job = {"company_name": "Sample Fake Name"}

        result = evaluate_rules(
            mca_result=mca,
            matching_result=matching,
            job_details=job,
        )

        self.assertLess(result["risk_score"], 51)
        self.assertEqual(result["risk_score"], 45)
        self.assertEqual(result["risk_level"], "HIGH")

    def test_no_job_message_does_not_trigger_message_rules(self):
        """Verify message-based rules do not trigger when job_message is omitted."""
        mca = {"status": "Active", "cin": "U12345"}
        matching = {"score": 95.0, "best_match": {"name": "GENUINE CORP"}, "no_match": False}
        job = {"company_name": "Genuine Corp"}

        result = evaluate_rules(
            mca_result=mca,
            matching_result=matching,
            job_details=job,
        )

        triggered_rule_names = {r["rule"] for r in result["triggered_rules"]}
        self.assertNotIn("upfront_payment_demanded", triggered_rule_names)
        self.assertNotIn("urgency_pressure_tactics", triggered_rule_names)
        self.assertNotIn("sensitive_documents_requested", triggered_rule_names)
        self.assertEqual(result["risk_score"], 0)
        self.assertEqual(result["risk_level"], "LOW")


if __name__ == "__main__":
    unittest.main()
