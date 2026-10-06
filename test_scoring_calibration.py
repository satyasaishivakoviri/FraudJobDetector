import unittest
from datetime import datetime, timedelta

from app.utils.scoring import (
    ALL_RULES,
    evaluate_rules,
    rule_address_mismatch,
    rule_entity_incorporation_vs_claimed_scale,
    rule_free_hosting_or_tld,
    rule_no_registry_match,
    rule_udyam_absent_for_small_business,
    rule_upfront_payment_demanded,
)


class TestEntityIncorporationVsClaimedScale(unittest.TestCase):
    def test_recent_incorporation_claiming_mnc_triggers_25(self):
        mca = {
            "company_name": "APEX BUSINESS SOLUTIONS PRIVATE LIMITED",
            "cin": "U74999DL2024PTC987654",
            "status": "Active",
            "entity_age_days": 120,  # 4 months ago
            "incorporation_date": (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d"),
        }
        job = {
            "company_name": "Apex Business Solutions Pvt Ltd",
            "claims_mnc": True,
            "claimed_address": "Offices in 15 countries",
        }
        triggered, weight, reason = rule_entity_incorporation_vs_claimed_scale(
            gst={}, mca=mca, udyam={}, domain={}, matching={}, job=job
        )
        self.assertTrue(triggered)
        self.assertEqual(weight, 25)
        self.assertIn("established MNC/global enterprise", reason)
        self.assertIn("< 1 year", reason)

    def test_established_incorporation_claiming_mnc_does_not_trigger(self):
        mca = {
            "company_name": "GLOBAL TECH LIMITED",
            "cin": "U72200MH2010PLC123456",
            "status": "Active",
            "entity_age_days": 4000,
            "incorporation_date": "2010-01-15",
        }
        job = {
            "company_name": "Global Tech Limited",
            "claims_mnc": True,
        }
        triggered, weight, reason = rule_entity_incorporation_vs_claimed_scale(
            gst={}, mca=mca, udyam={}, domain={}, matching={}, job=job
        )
        self.assertFalse(triggered)
        self.assertEqual(weight, 25)
        self.assertEqual(reason, "")

    def test_recent_incorporation_claiming_startup_does_not_trigger(self):
        mca = {
            "company_name": "ROBOTICS LABS PRIVATE LIMITED",
            "cin": "U29299TG2024PTC178901",
            "status": "Active",
            "entity_age_days": 100,
        }
        job = {
            "company_name": "Robotics Labs",
            "claims_mnc": False,
            "company_scale": "small",
        }
        triggered, weight, reason = rule_entity_incorporation_vs_claimed_scale(
            gst={}, mca=mca, udyam={}, domain={}, matching={}, job=job
        )
        self.assertFalse(triggered)


class TestAddressMismatchResidentialEnterprise(unittest.TestCase):
    def test_residential_flat_with_claimed_global_hq_triggers_15(self):
        mca = {
            "company_name": "APEX BUSINESS SOLUTIONS PRIVATE LIMITED",
            "registered_office_address": "Flat No 102, Residential Colony, Delhi",
        }
        job = {
            "company_name": "Apex Business Solutions Pvt Ltd",
            "claims_mnc": True,
            "claimed_address": "Offices in 15 countries",
        }
        triggered, weight, reason = rule_address_mismatch(
            gst={}, mca=mca, udyam={}, domain={}, matching={}, job=job
        )
        self.assertTrue(triggered)
        self.assertEqual(weight, 15)
        self.assertIn("residential flat/shell address", reason)

    def test_standard_state_mismatch_triggers_10(self):
        gst = {"state": "Maharashtra"}
        job = {
            "company_name": "TransGlobal Financial Services",
            "claimed_state": "Karnataka",
        }
        triggered, weight, reason = rule_address_mismatch(
            gst=gst, mca={}, udyam={}, domain={}, matching={}, job=job
        )
        self.assertTrue(triggered)
        self.assertEqual(weight, 10)
        self.assertIn("does not match registered state", reason)

    def test_matching_address_does_not_trigger(self):
        gst = {"state": "Karnataka"}
        mca = {"registered_office_address": "MG Road, Bengaluru, Karnataka"}
        job = {
            "company_name": "Nexora Cloud Systems Pvt Ltd",
            "claimed_state": "Karnataka",
        }
        triggered, weight, reason = rule_address_mismatch(
            gst=gst, mca=mca, udyam={}, domain={}, matching={}, job=job
        )
        self.assertFalse(triggered)
        self.assertEqual(weight, 10)


class TestUdyamAbsentSuppression(unittest.TestCase):
    def test_udyam_absent_suppressed_when_mca_and_gst_active(self):
        mca = {"cin": "U29299TG2023PTC178901", "status": "Active"}
        gst = {"legal_name": "ORBITALS ROBOTICS PRIVATE LIMITED", "status": "Active"}
        udyam = {"registered": False, "status": "not_registered"}
        job = {
            "company_name": "Orbitals Robotics Pvt Ltd",
            "company_scale": "small",
            "claims_msme": True,
        }
        triggered, weight, reason = rule_udyam_absent_for_small_business(
            gst=gst, mca=mca, udyam=udyam, domain={}, matching={}, job=job
        )
        self.assertFalse(triggered)
        self.assertEqual(weight, 0)
        self.assertEqual(reason, "")

    def test_udyam_absent_penalizes_when_mca_and_gst_not_verified(self):
        mca = {}
        gst = {}
        udyam = {"registered": False, "status": "not_registered"}
        job = {
            "company_name": "Local Craft Store",
            "company_scale": "small",
            "claims_msme": True,
        }
        triggered, weight, reason = rule_udyam_absent_for_small_business(
            gst=gst, mca=mca, udyam=udyam, domain={}, matching={}, job=job
        )
        self.assertTrue(triggered)
        self.assertEqual(weight, 5)
        self.assertIn("Employer claims to be a small/local MSME enterprise", reason)


class TestFreeHostingOrTLD(unittest.TestCase):
    def test_blogspot_triggers_20(self):
        domain = {"domain": "primecareerboosters.blogspot.com"}
        job = {}
        triggered, weight, reason = rule_free_hosting_or_tld(
            gst={}, mca={}, udyam={}, domain=domain, matching={}, job=job
        )
        self.assertTrue(triggered)
        self.assertEqual(weight, 20)
        self.assertIn("free website builder", reason)

    def test_wixsite_triggers_20(self):
        domain = {"domain": "nextgencareershub.wixsite.com"}
        job = {}
        triggered, weight, reason = rule_free_hosting_or_tld(
            gst={}, mca={}, udyam={}, domain=domain, matching={}, job=job
        )
        self.assertTrue(triggered)
        self.assertEqual(weight, 20)
        self.assertIn("free website builder", reason)

    def test_tk_tld_triggers_20(self):
        domain = {"domain": "skywavetechjobs.tk"}
        job = {}
        triggered, weight, reason = rule_free_hosting_or_tld(
            gst={}, mca={}, udyam={}, domain=domain, matching={}, job=job
        )
        self.assertTrue(triggered)
        self.assertEqual(weight, 15)
        self.assertIn("TLD", reason)

    def test_legitimate_custom_domain_does_not_trigger(self):
        domain = {"domain": "vertexsoftware.in"}
        job = {}
        triggered, weight, reason = rule_free_hosting_or_tld(
            gst={}, mca={}, udyam={}, domain=domain, matching={}, job=job
        )
        self.assertFalse(triggered)
        self.assertEqual(weight, 20)


class TestOverallScoringEngine(unittest.TestCase):
    def test_apex_business_solutions_now_evaluates_to_high_risk(self):
        # The key mismatch from Prompt 11 calibration report
        mca = {
            "company_name": "APEX BUSINESS SOLUTIONS PRIVATE LIMITED",
            "cin": "U74999DL2024PTC987654",
            "status": "Active",
            "entity_age_days": 120,
            "incorporation_date": (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d"),
            "registered_office_address": "Flat No 102, Residential Colony, Delhi",
        }
        domain = {
            "domain": "apexbusiness-careers.net",
            "domain_age_days": 60,
            "ssl_status": "valid",
        }
        matching = {
            "claimed_name": "Apex Business Solutions Pvt Ltd",
            "best_match": {"name": "APEX BUSINESS SOLUTIONS PRIVATE LIMITED"},
            "score": 95.0,
            "no_match": False,
        }
        job = {
            "company_name": "Apex Business Solutions Pvt Ltd",
            "claims_mnc": True,
            "claims_established": True,
            "claimed_address": "Offices in 15 countries",
            "contact_email": "hr@apexbusiness-careers.net",
        }

        res = evaluate_rules(
            gst_result={},
            mca_result=mca,
            udyam_result={"registered": False},
            domain_result=domain,
            matching_result=matching,
            job_details=job,
        )

        # Expected triggers:
        # - domain_age_under_3_months: +20
        # - address_mismatch (residential vs enterprise): +15
        # - entity_incorporation_vs_claimed_scale: +25
        # Total: 60 -> High risk!
        self.assertGreaterEqual(res["risk_score"], 51)
        self.assertEqual(res["risk_band"], "High risk (strong warning to user)")

    def test_orbitals_robotics_now_scores_zero(self):
        # Case 15: young startup with active MCA + GST should no longer be penalized
        mca = {
            "company_name": "ORBITALS ROBOTICS PRIVATE LIMITED",
            "cin": "U29299TG2023PTC178901",
            "status": "Active",
            "incorporation_date": "2023-09-01",
        }
        gst = {
            "legal_name": "ORBITALS ROBOTICS PRIVATE LIMITED",
            "status": "Active",
            "state": "Telangana",
        }
        domain = {
            "domain": "orbitalsrobotics.in",
            "domain_age_days": 1100,
            "ssl_status": "valid",
        }
        matching = {
            "claimed_name": "Orbitals Robotics Pvt Ltd",
            "best_match": {"name": "ORBITALS ROBOTICS PRIVATE LIMITED"},
            "score": 95.0,
            "no_match": False,
        }
        job = {
            "company_name": "Orbitals Robotics Pvt Ltd",
            "contact_email": "hello@orbitalsrobotics.in",
            "company_scale": "small",
            "claims_msme": True,
            "has_linkedin_presence": True,
            "upfront_fee_demanded": False,
        }

        res = evaluate_rules(
            gst_result=gst,
            mca_result=mca,
            udyam_result={"registered": False},
            domain_result=domain,
            matching_result=matching,
            job_details=job,
        )
        self.assertEqual(res["risk_score"], 0)
        self.assertEqual(res["risk_band"], "Low risk")


if __name__ == "__main__":
    unittest.main()
