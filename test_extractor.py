import unittest
from app.utils.extractor import extract_entities


class TestExtractEntities(unittest.TestCase):
    def test_extract_gstin_and_cin(self):
        text = """
        Company: Vertex Software Solutions Pvt Ltd
        CIN: U72200MH2016PTC288123
        GSTIN: 24AAACT2727Q1ZW
        Domain: vertexsoftware.in
        Email: hr@vertexsoftware.in
        Role: Backend Developer Intern, ₹15,000/month stipend
        """
        res = extract_entities(text)
        self.assertEqual(res["company_name"], "Vertex Software Solutions Pvt Ltd")
        self.assertEqual(res["company_name_confidence"], "high")
        self.assertEqual(res["gstin"], "24AAACT2727Q1ZW")
        self.assertEqual(res["gstin_confidence"], "high")
        self.assertEqual(res["cin"], "U72200MH2016PTC288123")
        self.assertEqual(res["cin_confidence"], "high")
        self.assertEqual(res["email_address"], "hr@vertexsoftware.in")
        self.assertEqual(res["email_address_confidence"], "high")
        self.assertEqual(res["domain_or_url"], "vertexsoftware.in")
        self.assertEqual(res["domain_or_url_confidence"], "high")
        self.assertIn("15,000", res["stated_salary_or_stipend"])
        self.assertEqual(res["stated_salary_or_stipend_confidence"], "high")

    def test_extract_phone_and_free_subdomain(self):
        text = """
        URGENT HIRING: Prime Career Boosters
        Apply at: primecareerboosters.blogspot.com
        Guaranteed Placement fee: Rs. 5,000
        Contact us on WhatsApp: +91 98765 43210
        """
        res = extract_entities(text)
        self.assertEqual(res["company_name"], "Prime Career Boosters")
        self.assertEqual(res["company_name_confidence"], "high")
        self.assertEqual(res["domain_or_url"], "primecareerboosters.blogspot.com")
        self.assertEqual(res["domain_or_url_confidence"], "high")
        self.assertIsNotNone(res["phone_number"])
        self.assertEqual(res["phone_number_confidence"], "high")
        self.assertIn("5,000", res["stated_salary_or_stipend"])

    def test_extract_from_unstructured_offer_email(self):
        text = """
        Hi Candidate,
        Congratulations! You have been selected for the Data Entry Work From Home role at Global Tech MNC Solutions.
        Your monthly payout will be ₹40,000/month.
        Please send your resume to recruiter.hr2024@gmail.com or visit https://globaltechmncjobs.xyz/careers.
        Call us at 9876543210.
        """
        res = extract_entities(text)
        self.assertEqual(res["company_name"], "Global Tech MNC Solutions")
        self.assertEqual(res["company_name_confidence"], "high")
        self.assertEqual(res["domain_or_url"], "globaltechmncjobs.xyz")
        self.assertEqual(res["email_address"], "recruiter.hr2024@gmail.com")
        self.assertEqual(res["email_address_confidence"], "high")
        self.assertIsNotNone(res["phone_number"])
        self.assertEqual(res["phone_number_confidence"], "high")
        self.assertIn("40,000", res["stated_salary_or_stipend"])

    def test_empty_and_noise_text(self):
        res = extract_entities("")
        self.assertIsNone(res["company_name"])
        self.assertEqual(res["company_name_confidence"], "none")
        self.assertIsNone(res["gstin"])
        self.assertIsNone(res["domain_or_url"])

    def test_llp_company_heuristic(self):
        text = "Welcome to Brightpath Consulting LLP. Your stipend is 8,000/pm."
        res = extract_entities(text)
        self.assertEqual(res["company_name"], "Brightpath Consulting LLP")
        self.assertEqual(res["company_name_confidence"], "high")
        self.assertIn("8,000", res["stated_salary_or_stipend"])


if __name__ == "__main__":
    unittest.main()
