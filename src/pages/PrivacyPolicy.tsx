import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ArrowLeft, Lock, EyeOff, Server, Clock, Database, CheckCircle2 } from "lucide-react";

const GREEN_BG_STYLE: React.CSSProperties = {
  background: "#0b3b2a",
  backgroundImage:
    "radial-gradient(circle at 18% 8%, rgba(68,125,98,.72), transparent 34%), radial-gradient(circle at 82% 20%, rgba(251,251,250,.12), transparent 28%), radial-gradient(circle at 48% 78%, rgba(9,48,35,.5), transparent 44%), linear-gradient(135deg,#0b3b2a 0%,#14573f 48%,#082d22 100%)",
  minHeight: "100vh",
};

export const PrivacyPolicy: React.FC = () => {
  return (
    <div style={GREEN_BG_STYLE} className="text-[#fbfbfa] flex flex-col font-sans">
      <header className="bg-[#0b3b2a]/80 backdrop-blur-md border-b border-[rgba(251,251,250,0.15)] py-3.5 px-6 sticky top-0 z-30 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-[8px] bg-[#142b22] text-[#fbfbfa] border border-[rgba(251,251,250,0.2)] flex items-center justify-center font-bold shadow-xs">
              <ShieldCheck className="w-4 h-4 text-emerald-300" />
            </div>
            <div>
              <div className="font-bold text-base tracking-tight leading-tight text-[#fbfbfa]">
                FraudJobDetector
              </div>
              <div className="text-[10px] font-bold text-[rgba(251,251,250,0.65)] uppercase tracking-widest">
                Due Diligence Engine
              </div>
            </div>
          </Link>
          <Link
            to="/"
            className="text-xs font-medium text-[rgba(251,251,250,0.8)] hover:text-[#fff] flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-[#142b22] border border-[#10261d] hover:bg-[#204434] transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Scanner
          </Link>
        </div>
      </header>

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-10 sm:py-12">
        <div className="mb-8">
          <div className="text-xs font-bold text-emerald-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-emerald-300" /> Compliance and Data Governance
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-[#fbfbfa] tracking-tight">
            Privacy Policy
          </h1>
          <p className="text-xs text-[rgba(251,251,250,0.7)] mt-2">
            Last Updated: September 2026. Effective Immediately.
          </p>
        </div>

        <div className="space-y-6 text-xs sm:text-sm text-[rgba(251,251,250,0.9)] leading-relaxed">
          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <EyeOff className="w-4 h-4 text-emerald-300" /> 1. Ephemeral In-Memory Processing Guarantee
            </h2>
            <p className="mb-3">
              FraudJobDetector is engineered with an ephemeral privacy-first architecture. Any job postings, recruiter communications, offer letters, or screenshots uploaded to our platform are processed in volatile memory solely for entity extraction and statutory cross-referencing.
            </p>
            <ul className="space-y-2 list-disc pl-5 text-[rgba(251,251,250,0.75)]">
              <li>Uploaded documents and images are never retained on permanent disk storage.</li>
              <li>We do not build candidate profiles, behavioral graphs, or marketing pools.</li>
              <li>We do not sell, rent, or monetize personal candidate information under any circumstances.</li>
            </ul>
          </section>

          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-300" /> 2. Automatic Candidate PII Redaction
            </h2>
            <p className="mb-3">
              When analyzing recruitment communications and offer letters, our entity extraction engine automatically isolates company identification tokens (CIN, GSTIN, company name, corporate domain) while ignoring and redacting sensitive candidate personal data:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-[#fbfbfa]">
              <div className="p-3 bg-[#082d22] rounded-lg border border-[rgba(251,251,250,0.18)] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-300 shrink-0" />
                <span>Candidate Aadhaar, PAN, and identity numbers</span>
              </div>
              <div className="p-3 bg-[#082d22] rounded-lg border border-[rgba(251,251,250,0.18)] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-300 shrink-0" />
                <span>Personal bank account and UPI identifiers</span>
              </div>
              <div className="p-3 bg-[#082d22] rounded-lg border border-[rgba(251,251,250,0.18)] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-300 shrink-0" />
                <span>Private personal residential addresses</span>
              </div>
              <div className="p-3 bg-[#082d22] rounded-lg border border-[rgba(251,251,250,0.18)] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-300 shrink-0" />
                <span>Private mobile phone and personal contact entries</span>
              </div>
            </div>
          </section>

          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-emerald-300" /> 3. Temporary Shareable Reports (7-Day TTL)
            </h2>
            <p className="mb-3">
              If you generate a shareable verification report link:
            </p>
            <ul className="space-y-2 list-disc pl-5 text-[rgba(251,251,250,0.75)]">
              <li>Each shared report is assigned an unguessable, cryptographically generated token.</li>
              <li>Shared reports have a strict, non-extendable Time-To-Live of 7 days, after which they are permanently expunged.</li>
              <li>You may instantly revoke any shared report at any time using the Revoke control.</li>
              <li>Shared reports display strictly verified employer evidence and risk indicators, never candidate personal details.</li>
            </ul>
          </section>

          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-300" /> 4. Statutory Registry Inquiries
            </h2>
            <p>
              To confirm company legitimacy, our servers submit programmatic lookup requests to publicly accessible statutory registries, including the Ministry of Corporate Affairs (MCA), the Goods and Services Tax Network (GSTN), and the Udyam MSME portal. These queries transmit only corporate identifiers (such as company legal names, stated CIN, or GSTIN). No candidate information is transmitted to government registries.
            </p>
          </section>

          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <Server className="w-4 h-4 text-emerald-300" /> 5. Zero Tracking Cookies and Ad Tech
            </h2>
            <p>
              FraudJobDetector employs no advertising cookies, no third-party cross-site trackers, and no analytics tracking scripts that monitor candidate browsing outside this application. All local storage usage is restricted to functional state management for active verification sessions.
            </p>
          </section>
        </div>
      </main>

      <footer className="border-t border-[rgba(251,251,250,0.15)] bg-[rgba(8,45,34,0.85)] py-6 text-center text-xs text-[rgba(251,251,250,0.65)] mt-auto">
        <div className="max-w-4xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            FraudJobDetector • Independent Corporate Identity & Recruitment Due Diligence Engine
          </div>
          <div className="flex items-center gap-4 text-xs">
            <Link to="/" className="text-[rgba(251,251,250,0.65)] hover:text-[#fff] transition">
              Scanner Console
            </Link>
            <Link to="/terms" className="text-[rgba(251,251,250,0.65)] hover:text-[#fff] transition">
              Terms & Conditions
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PrivacyPolicy;
