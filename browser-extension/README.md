# Fraud Job Detector — Chrome & Chromium Extension (Manifest V3)

The **Fraud Job Detector** browser extension allows job seekers to instantly verify job postings directly from LinkedIn, job boards, or recruiter pages without leaving their browser.

---

## 🚀 Key Features

1. **Manifest V3 Architecture**: Secure, modern service-worker architecture compliant with Chromium standards.
2. **Explicit Verification Flow**:
   - Displays a clean welcome screen with **`[ Verify this job ]`**.
   - **Never** sends data automatically without user initiation.
   - Extracts publicly visible job details (Schema.org microdata, OpenGraph, LinkedIn selectors).
3. **Editable Review Screen**:
   - Allows users to inspect and edit extracted Company Name, Domain, Recruiter Email, Job Title, and Fee Demands before running verification.
4. **Compact Result Card**:
   - **Risk Level** (LOW / MEDIUM / HIGH badge)
   - **Risk Score** (/100)
   - Company Name
   - Warning Signals list
   - Structured Safety Recommendations
5. **One-Click Full Report**:
   - **`[ Open Full Report ]`** opens the full corporate due diligence report on the local server (`http://127.0.0.1:8000/results?token=...`).

---

## 🛠️ How to Install in Chrome / Edge / Brave

1. Open your Chromium-based browser and navigate to:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
   - Brave: `brave://extensions`
2. Toggle **Developer mode** in the top-right corner.
3. Click **Load unpacked**.
4. Select the `browser-extension/` directory from this project (`fraud-job-detector/browser-extension`).
5. The **Fraud Job Detector** shield icon will appear in your browser toolbar. Pin it for quick access.

---

## 🧪 Testing the Extension

1. Ensure the FastAPI backend is running:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
2. Navigate to any job posting (e.g. on LinkedIn, Indeed, Naukri, or a test page).
3. Click the **Fraud Job Detector** extension icon.
4. Click **`[ Verify this job ]`**.
5. Review the extracted company name and details. Edit if needed.
6. Click **`[ Run Verification ]`**.
7. View the compact risk score, warning signals, and click **`[ Open Full Report ]`** to see the full corporate due diligence findings.