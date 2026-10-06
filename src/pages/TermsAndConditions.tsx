import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ArrowLeft, FileCheck2, AlertTriangle, ShieldAlert } from "lucide-react";

const GREEN_BG_STYLE: React.CSSProperties = {
  background: "#0b3b2a",
  backgroundImage:
    "radial-gradient(circle at 18% 8%, rgba(68,125,98,.72), transparent 34%), radial-gradient(circle at 82% 20%, rgba(251,251,250,.12), transparent 28%), radial-gradient(circle at 48% 78%, rgba(9,48,35,.5), transparent 44%), linear-gradient(135deg,#0b3b2a 0%,#14573f 48%,#082d22 100%)",
  minHeight: "100vh",
};

export const TermsAndConditions: React.FC = () => {
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
            <FileCheck2 className="w-3.5 h-3.5 text-emerald-300" /> Statutory Due Diligence Governance
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-[#fbfbfa] tracking-tight">
            Terms and Conditions
          </h1>
          <p className="text-xs text-[rgba(251,251,250,0.7)] mt-2">
            Last Updated: September 2026. Effective Immediately.
          </p>
        </div>

        <div className="space-y-6 text-xs sm:text-sm text-[rgba(251,251,250,0.9)] leading-relaxed">
          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-emerald-300" /> 1. Nature of the Due Diligence Service
            </h2>
            <p className="mb-3">
              FraudJobDetector provides automated statutory cross-referencing and heuristic risk scoring for employment opportunities, recruitment communications, and offer documentation. The platform evaluates claims against public records from official registries including the Ministry of Corporate Affairs (MCA), the Goods and Services Tax Network (GSTN), the Udyam MSME registry, and public DNS/WHOIS databases.
            </p>
            <p>
              By accessing or using FraudJobDetector, you acknowledge and agree that verification reports represent point-in-time heuristic evaluations derived from public data availability.
            </p>
          </section>

          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" /> 2. Disclaimer of Legal and Financial Counsel
            </h2>
            <p className="mb-3">
              FraudJobDetector is a technical due diligence tool, not a legal advisory firm or licensed investigative agency. Nothing contained in our verification reports, risk scores, or safety recommendations constitutes formal legal, financial, or employment advice.
            </p>
            <p>
              Users are advised to exercise independent judgement, cross-check official corporate career portals, and report criminal extortion or impersonation attempts directly to state or national cybercrime authorities (e.g., cybercrime.gov.in).
            </p>
          </section>

          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-emerald-300" /> 3. Acceptable Use and Abuse Prevention
            </h2>
            <p className="mb-3">
              You agree to use FraudJobDetector exclusively for bona fide employment due diligence. The following activities are strictly prohibited:
            </p>
            <ul className="space-y-2 list-disc pl-5 text-[rgba(251,251,250,0.75)]">
              <li>Automated scraping, denial of service attacks, or systematic extraction of platform data.</li>
              <li>Submitting defamatory, harassing, or unlawfully obtained confidential records.</li>
              <li>Attempting to bypass rate limiting, security controls, or report expiration constraints.</li>
              <li>Using verification results to extort, harass, or defame legitimate commercial entities.</li>
            </ul>
          </section>

          <section className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
            <h2 className="text-base font-bold text-[#fbfbfa] mb-3">4. Limitation of Liability</h2>
            <p className="mb-3">
              In no event shall FraudJobDetector, its operators, or developers be held liable for any direct, indirect, incidental, or consequential damages resulting from:
            </p>
            <ul className="space-y-2 list-disc pl-5 text-[rgba(251,251,250,0.75)]">
              <li>Inaccuracies, downtime, or omissions in third-party government registries (MCA, GSTN, Udyam).</li>
              <li>Decisions made regarding accepting, rejecting, or evaluating employment opportunities.</li>
              <li>Any financial losses incurred by users through external fraudulent recruiters or scammers.</li>
            </ul>
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
            <Link to="/privacy" className="text-[rgba(251,251,250,0.65)] hover:text-[#fff] transition">
              Privacy Policy
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default TermsAndConditions;
