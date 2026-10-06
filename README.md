# FraudJobDetector

<p align="center">
  <strong>Automated Corporate Due-Diligence & Employment Scam Detection Engine</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind CSS" />
  <img src="https://img.shields.io/badge/Vite-6.0-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/Tests-67%20Passed-brightgreen?style=for-the-badge" alt="Tests" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License" />
</p>

---

## Overview

**FraudJobDetector** is an open-source, full-stack cybersecurity and due-diligence platform engineered to safeguard job seekers and students against recruitment scams, fraudulent offer letters, and corporate impersonation.

The platform ingests suspicious job communications across multiple channels—**pasted text / WhatsApp messages**, **uploaded PDF/DOCX offer letters**, **image screenshots**, or via a **Chrome/Edge browser extension**. It extracts critical metadata using a deterministic NLP and OCR engine, cross-references corporate entities in real time against Indian statutory registries (**Ministry of Corporate Affairs / MCA**, **GSTIN**, **MSME Udyam**), performs network and SSL/WHOIS cyber-infrastructure checks, and computes an explainable, calibrated fraud risk score with actionable safety guidance.

---

## Key Features

### 1. Multi-Modal Ingestion Pipeline
* **Pasted Text & Chat Messages**: Analyzes unformatted job descriptions, recruiter WhatsApp/Telegram messages, and emails.
* **Document Parser (PDF & DOCX)**: Multi-page text extraction combining digital document structures with automated fallback OCR for scanned pages.
* **Image OCR with Dynamic Rescaling**: Hardware-accelerated native OCR with LANCZOS upscaling for high-fidelity character recognition on low-resolution screenshot crops.
* **Browser Extension (Manifest V3)**: One-click job verification directly within portals like LinkedIn, Naukri, and Indeed.

### 2. High-Precision Deterministic Entity Extraction
* Self-contained, deterministic NLP extraction for:
  * Company names (including modern brands like *Stripe*, *Swiggy*, *Zepto* lacking traditional corporate suffixes).
  * Job designations, stated salaries, stipends, and work modes (Remote, Hybrid, On-site).
  * Statutory identifiers: 15-character **GSTIN**, 21-character **CIN**, and **Udyam** MSME numbers.
  * Direct contact coordinates (recruiter emails, domains, phone numbers).
* **Automated Text Normalization**: Resolves OCR split emails (`careers @ tcscom` -> `careers@tcs.com`), hyphenated line breaks, and smart quotes.

### 3. Statutory Registry Cross-Referencing
* **MCA / ROC Master Data**: Real-time corporate registration check via Sandbox KYC API with automated failover to `data.gov.in`. Identifies company status (`Active`, `Strike Off`, `Dissolved`), incorporation date, CIN, registered office, and directors.
* **GSTIN Taxpayer Verification**: Validates active GST status, legal trade name, and jurisdiction.
* **MSME Udyam Registry**: Verifies registered micro, small, and medium enterprises.
* **RapidFuzz Fuzzy Matching**: Token-sort Levenshtein similarity algorithm prevents false mismatches due to minor word reorderings or legal suffixes (`Pvt Ltd`, `LLP`).

### 4. Cyber-Infrastructure & Domain Verification
* **TLS / SSL Socket Handshake**: Direct port 443 handshake to verify SSL certificates (`valid`, `expired`, `self-signed`, `invalid`).
* **WHOIS Domain Age**: Computes domain registration age; flags domains created < 90 days ago.
* **Disposable & High-Risk TLDs**: Flags low-cost, disposable extensions frequently abused in scams (`.xyz`, `.top`, `.tk`, `.buzz`, `.club`, `.work`).
* **Corporate Impersonation Detector**: Whitelists official enterprise domains (e.g. *Microsoft*, *Google*, *Amazon*, *TCS*, *Infosys*) and detects lookalike domains (e.g. `microsoft-india-careers.xyz`).

### 5. Explainable Risk Scoring Engine
* Transparent, weighted evaluation of 12+ risk signals:
  * **Upfront payment demanded** (+35 points)
  * **MCA company struck off / inactive** (+25 points)
  * **Major company impersonation** (+25 points)
  * **Company name discrepancy** (+20 points)
  * **Suspicious lookalike domain** (+20 points)
  * **Recently registered domain (< 90 days)** (+15 points)
  * **Free/public email provider for corporate hiring** (+15 points)
  * **Sensitive identity documents requested upfront** (+15 points)
  * **Suspicious TLD** (+15 points)
  * **SSL missing or invalid** (+10 points)
  * **Urgency / high-pressure language** (+10 points)
  * **WHOIS privacy proxy active** (+5 points)
* **Risk Categorization**:
  * `LOW` (0 - 29): Legitimate corporate and infrastructure signals.
  * `MEDIUM` (30 - 59): Uncorroborated details, missing statutory IDs, or domain warnings.
  * `HIGH` (60+): Critical fraud indicators (demanded fees, struck-off status, impersonation).

### 6. Privacy-Preserving Shareable Reports
* Generates cryptographic, tokenized share links (`secrets.token_urlsafe`) valid for 7 days.
* **Automatic PII Sanitization**: Strips candidate resumes, personal emails, phone numbers, and document bytes—storing only public statutory due diligence findings in an SQLite database.
* One-click report revocation for owners.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              CLIENT TIER                               │
│  React 18 + TypeScript + Vite + Tailwind CSS | Chrome/Edge Extension   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (Vite Proxy :5173 -> :8000)
┌───────────────────────────────────▼────────────────────────────────────┐
│                              API GATEWAY                               │
│                FastAPI (ASGI) + Uvicorn + Pydantic v2                  │
└───────┬───────────────────────────┬───────────────────────────┬────────┘
        │                           │                           │
┌───────▼─────────────┐   ┌─────────▼─────────────┐   ┌─────────▼────────┐
│ INGESTION & OCR     │   │ STATUTORY VERIFIERS   │   │ SCORING ENGINE   │
│ - pypdf             │   │ - MCA / ROC API       │   │ - 12+ Rules      │
│ - python-docx       │   │ - GSTIN Lookup        │   │ - RapidFuzz      │
│ - Windows Native OCR│   │ - MSME Udyam          │   │ - Brand Matching │
│ - Text Normalizer   │   │ - SSL / WHOIS Engine  │   │ - Calibrated Risk│
└─────────────────────┘   └───────────────────────┘   └─────────┬────────┘
                                                                │
                                                      ┌─────────▼────────┐
                                                      │ PERSISTENCE      │
                                                      │ SQLite (reports) │
                                                      └──────────────────┘
```

---

## Project Structure

```
FraudJobDetector/
├── app/
│   ├── models/                # Pydantic schemas (report, verification)
│   ├── services/
│   │   ├── extraction_service.py   # Unified deterministic NLP extraction engine
│   │   └── verification_service.py # Orchestrator for MCA, GST, WHOIS, scoring
│   ├── utils/
│   │   ├── document_parser.py      # PDF, DOCX, and OCR handling
│   │   ├── extractor.py            # Backward-compatible entity extractors
│   │   ├── identity.py             # Company identity resolution
│   │   ├── matching.py             # RapidFuzz fuzzy name similarity
│   │   ├── offer_consistency.py    # Offer letter term consistency checks
│   │   ├── recommendations.py      # Dynamic safety recommendation generator
│   │   ├── sandbox_client.py       # Sandbox.co.in authenticated HTTP client
│   │   ├── scoring.py              # Calibrated 12-rule fraud risk scoring engine
│   │   └── screenshot_analyzer.py  # Image screenshot signal extraction
│   ├── verifiers/
│   │   ├── domain.py               # WHOIS age, TLS socket check, TLD analysis
│   │   ├── gst.py                  # GSTIN format & status validator
│   │   ├── mca.py                  # MCA master data via Sandbox & data.gov.in
│   │   └── udyam.py                # MSME Udyam registration validator
│   ├── database.py            # SQLite schema, sanitization, token management
│   └── main.py                # FastAPI routes, middleware, and entry point
├── browser-extension/         # Manifest V3 extension for LinkedIn/Naukri
├── src/
│   ├── components/ui/         # React UI components (Hero, Loaders, Portals)
│   ├── pages/
│   │   ├── Home.tsx           # Multi-modal input hub
│   │   ├── Review.tsx         # Entity inspection and validation guard
│   │   ├── Results.tsx        # Risk scorecard, statutory cards & reports
│   │   ├── PrivacyPolicy.tsx  # Compliance & privacy terms
│   │   └── TermsAndConditions.tsx
│   ├── App.tsx                # React Router v6 routing table
│   └── main.tsx               # React DOM bootstrapping
├── tests/                     # Unit test suites (67 test cases)
├── requirements.txt           # Python backend dependencies
├── package.json               # Node.js frontend dependencies
├── vite.config.ts             # Vite dev server & backend reverse proxy
└── tailwind.config.js         # Tailwind theme configuration
```

---

## Getting Started

### Prerequisites
* **Python**: 3.10 or higher
* **Node.js**: 18.0 or higher
* **npm**: 9.0 or higher

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/satyasaishivakoviri/FraudJobDetector.git
cd FraudJobDetector

# Create and activate a Python virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Configure your `.env` file:
```env
HOST=127.0.0.1
PORT=8000
ENVIRONMENT=development

# Optional Sandbox.co.in API credentials (for live MCA/GST verification)
SANDBOX_API_KEY=your_sandbox_api_key_here
SANDBOX_API_SECRET=your_sandbox_api_secret_here

# Optional data.gov.in API key (for MCA fallback lookup)
DATAGOV_API_KEY=your_datagov_api_key_here
```

Start the FastAPI backend server:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The interactive Swagger API documentation will be available at:
`http://127.0.0.1:8000/docs`

---

### 2. Frontend Setup

In a separate terminal window:

```bash
# Install frontend dependencies
npm install

# Start the Vite development server
npm run dev
```
Open your browser and navigate to:
`http://127.0.0.1:5173`

---

### 3. Browser Extension Setup (Chrome / Edge / Brave)

1. Navigate to `chrome://extensions/` (or `edge://extensions/`).
2. Toggle **Developer mode** on (top-right).
3. Click **Load unpacked**.
4. Select the `browser-extension` folder inside this repository.
5. The FraudJobDetector icon will appear in your browser toolbar, ready to analyze active job tabs.

---

## Running the Automated Test Suite

FraudJobDetector includes a test suite covering document parsing, OCR normalization, statutory queries, entity extraction, and risk calibration:

```bash
# Run all 67 unit tests
python -m unittest discover -s . -p "test_*.py"
```

Verify frontend TypeScript compilation and build:
```bash
npm run build
```

---

## Core API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/extract-entities` | Extracts structured entities from raw job postings or emails. |
| `POST` | `/upload/offer-letter` | Ingests and extracts data from uploaded PDF/DOCX offer letters. |
| `POST` | `/upload/screenshot` | Ingests screenshots and runs OCR with image rescaling. |
| `POST` | `/check-company` | Runs statutory MCA, GST, Udyam, WHOIS/SSL checks and risk scoring. |
| `POST` | `/recheck-company` | Re-verifies an existing job check and computes delta differences. |
| `POST` | `/create-share-report` | Creates a sanitized, tokenized public verification report. |
| `GET` | `/api/report/{token}` | Fetches a sanitized public report by secure URL token. |
| `POST` | `/api/report/revoke` | Revokes an active public report before expiry. |
| `GET` | `/health` | Service health check. |

---

## Security & Privacy Principles

* **Data Minimization**: The platform does not store personal resumes, applicant phone numbers, or private emails.
* **Transient Memory Processing**: Document files uploaded for parsing are processed in memory and discarded.
* **Cryptographic Tokenization**: Public report links utilize cryptographically secure `secrets.token_urlsafe(24)` identifiers.
* **Automatic Expiration**: Reports expire automatically after 7 days in SQLite.

---

## Contributing

Contributions, bug reports, and feature suggestions are welcome!
1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/NewDetector`).
3. Commit your Changes (`git commit -m 'Add new scam detection heuristic'`).
4. Push to the Branch (`git push origin feature/NewDetector`).
5. Open a Pull Request.

---

## Author & Maintainer

**Satya Sai Shiva Koviri**  
* GitHub: [@satyasaishivakoviri](https://github.com/satyasaishivakoviri)  
* Repository: [FraudJobDetector](https://github.com/satyasaishivakoviri/FraudJobDetector)

---

## Disclaimer

*FraudJobDetector provides automated risk analysis and public corporate due diligence based on available public records and algorithmic heuristics. It does not constitute legal counsel or an absolute certification of employment legitimacy. Always conduct independent verification before sending funds or sensitive personal credentials.*
