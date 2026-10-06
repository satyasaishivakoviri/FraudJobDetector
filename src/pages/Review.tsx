import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Globe,
  Mail,
  Phone,
  Hash,
  DollarSign,
  MapPin,
  Briefcase,
  ShieldCheck,
  FileText,
  AlertCircle,
  Clock,
  Calendar,
  Video,
  Layers,
  GraduationCap
} from "lucide-react";

const GREEN_BG_STYLE: React.CSSProperties = {
  background: "#0b3b2a",
  backgroundImage:
    "radial-gradient(circle at 18% 8%, rgba(68,125,98,.72), transparent 34%), radial-gradient(circle at 82% 20%, rgba(251,251,250,.12), transparent 28%), radial-gradient(circle at 48% 78%, rgba(9,48,35,.5), transparent 44%), linear-gradient(135deg,#0b3b2a 0%,#14573f 48%,#082d22 100%)",
  minHeight: "100vh",
};

export const Review: React.FC = () => {
  const navigate = useNavigate();

  const [companyName, setCompanyName] = useState("");
  const [domain, setDomain] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [gstin, setGstin] = useState("");
  const [cin, setCin] = useState("");
  const [salary, setSalary] = useState("");
  const [role, setRole] = useState("");
  const [address, setAddress] = useState("");
  const [workMode, setWorkMode] = useState("");
  const [jobType, setJobType] = useState("");
  const [interviewMode, setInterviewMode] = useState("");
  const [experience, setExperience] = useState("");
  const [deadline, setDeadline] = useState("");
  const [rawText, setRawText] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("fjd_raw_message") || "";
    setRawText(raw);

    const storedEdited = sessionStorage.getItem("fjd_edited_entities");
    const storedExtracted = sessionStorage.getItem("fjd_extracted_entities");
    const storedOffer = sessionStorage.getItem("fjd_offer_letter_data");

    let initial: any = {};
    try {
      if (storedEdited) initial = JSON.parse(storedEdited);
      else if (storedExtracted) initial = JSON.parse(storedExtracted);
      else if (storedOffer) initial = JSON.parse(storedOffer);
    } catch (e) {}

    setCompanyName(initial.company_name || initial.company || "");
    setDomain(initial.company_domain || initial.claimed_domain || initial.domain || initial.domain_or_url || "");
    setEmail(initial.recruiter_email || initial.contact_email || initial.email_address || initial.email || "");
    setPhone(initial.recruiter_phone || initial.phone_number || initial.phone || "");
    setGstin(initial.gstin || "");
    setCin(initial.cin || "");
    setSalary(initial.stated_salary_or_stipend || initial.salary || initial.stipend || "");
    setRole(initial.job_title || initial.role || "");
    setAddress(initial.company_address || initial.work_location || initial.location || "");
    setWorkMode(initial.work_mode || "");
    setJobType(initial.job_type || initial.employment_type || "");
    setInterviewMode(initial.interview_mode || "");
    setExperience(initial.required_experience || "");
    setDeadline(initial.application_deadline || initial.joining_date || "");
  }, []);

  const handleContinue = () => {
    if (!companyName.trim()) {
      setValidationError("Company name is required to execute government statutory verification. Please enter or confirm the employer name before proceeding.");
      return;
    }
    setValidationError(null);

    const editedData = {
      company_name: companyName.trim(),
      claimed_domain: domain.trim(),
      domain_or_url: domain.trim(),
      company_domain: domain.trim(),
      contact_email: email.trim(),
      recruiter_email: email.trim(),
      email_address: email.trim(),
      phone_number: phone.trim(),
      recruiter_phone: phone.trim(),
      gstin: gstin.trim(),
      cin: cin.trim(),
      salary: salary.trim(),
      stated_salary_or_stipend: salary.trim(),
      role: role.trim(),
      job_title: role.trim(),
      company_address: address.trim(),
      work_location: address.trim(),
      work_mode: workMode.trim(),
      job_type: jobType.trim(),
      interview_mode: interviewMode.trim(),
      required_experience: experience.trim(),
      application_deadline: deadline.trim(),
    };

    sessionStorage.setItem("fjd_edited_entities", JSON.stringify(editedData));
    sessionStorage.setItem("fjd_pending_verification", "true");
    navigate("/results");
  };

  return (
    <div style={GREEN_BG_STYLE} className="text-[#fbfbfa] flex flex-col font-sans min-h-screen">
      {/* Header - Full Screen Width */}
      <header className="bg-[#0b3b2a]/80 backdrop-blur-md border-b border-[rgba(251,251,250,0.15)] py-3.5 px-4 sm:px-8 lg:px-12 sticky top-0 z-30 shadow-[0_4px_16px_rgba(0,0,0,0.15)] w-full">
        <div className="w-full max-w-[1500px] mx-auto flex items-center justify-between">
          <div
            onClick={() => navigate("/")}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-8 h-8 rounded-[8px] bg-[#142b22] text-[#fbfbfa] border border-[rgba(251,251,250,0.2)] flex items-center justify-center font-bold shadow-xs group-hover:bg-[#204434] transition">
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
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/")}
              className="text-xs font-medium px-3.5 py-1.5 rounded-[10px] bg-[#142b22] text-[#fbfbfa] border border-[#10261d] hover:bg-[#204434] transition shadow-xs"
            >
              Cancel Scan
            </button>
          </div>
        </div>
      </header>

      {/* Main Form Body - Expanded Full Screen Width */}
      <main className="flex-1 w-full max-w-[1500px] mx-auto px-4 sm:px-8 lg:px-12 py-8 sm:py-10">
        <div className="mb-6">
          <button
            onClick={() => navigate("/")}
            className="text-xs font-medium text-[rgba(251,251,250,0.7)] hover:text-[#fff] flex items-center gap-1.5 mb-2.5 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Scanner
          </button>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#fbfbfa] tracking-tight">
            Review Extracted Information
          </h1>
          <p className="text-xs text-[rgba(251,251,250,0.75)] mt-1.5 leading-relaxed">
            Verify and adjust the parameters extracted from your submission before executing statutory checks against government corporate registries.
          </p>
        </div>

        {validationError && (
          <div className="mb-6 p-4 rounded-xl bg-red-950/80 border border-red-500/50 text-red-200 text-xs flex items-center gap-3 shadow-md">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
            <div className="flex-1 font-medium">{validationError}</div>
          </div>
        )}

        {/* Full-width Responsive Workstation Panel */}
        <div className="w-full bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-2xl border border-[rgba(251,251,250,0.22)] p-6 sm:p-8 lg:p-10 shadow-[0_4px_24px_rgba(0,0,0,0.2)] space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-emerald-300" /> Company Name *
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => {
                  setCompanyName(e.target.value);
                  if (validationError) setValidationError(null);
                }}
                placeholder="e.g. Infosys, TCS, Tech Mahindra, Google"
                className={`w-full px-4 py-3 text-sm bg-[#082d22] border rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none transition ${
                  validationError && !companyName.trim()
                    ? "border-red-400 ring-1 ring-red-400"
                    : "border-[rgba(251,251,250,0.22)] focus:border-[#176247] focus:ring-1 focus:ring-[#176247]"
                }`}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-emerald-300" /> Claimed Domain / Website
              </label>
              <input
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="e.g. company.com"
                className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-emerald-300" /> Recruiter Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. hr@company.com"
                className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-emerald-300" /> Recruiter Phone
              </label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. +91 98765 43210"
                className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-emerald-300" /> GSTIN (Optional)
              </label>
              <input
                type="text"
                value={gstin}
                onChange={(e) => setGstin(e.target.value)}
                placeholder="15-character GSTIN"
                className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] font-mono focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-emerald-300" /> Corporate CIN (Optional)
              </label>
              <input
                type="text"
                value={cin}
                onChange={(e) => setCin(e.target.value)}
                placeholder="21-character CIN"
                className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] font-mono focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Briefcase className="w-3.5 h-3.5 text-emerald-300" /> Job Role / Title
              </label>
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. Software Engineer Intern, Data Analyst"
                className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <DollarSign className="w-3.5 h-3.5 text-emerald-300" /> Offered Salary / Stipend
              </label>
              <input
                type="text"
                value={salary}
                onChange={(e) => setSalary(e.target.value)}
                placeholder="e.g. ₹25,000 / month, 12 LPA"
                className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
              />
            </div>

            {/* Extended Modalities */}
            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-emerald-300" /> Work Mode & Job Type
              </label>
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  value={workMode}
                  onChange={(e) => setWorkMode(e.target.value)}
                  placeholder="e.g. Remote, Hybrid, On-site"
                  className="w-full px-3 py-2.5 text-xs bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] transition"
                />
                <input
                  type="text"
                  value={jobType}
                  onChange={(e) => setJobType(e.target.value)}
                  placeholder="e.g. Full-Time, Internship"
                  className="w-full px-3 py-2.5 text-xs bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Video className="w-3.5 h-3.5 text-emerald-300" /> Interview Mode / Deadline
              </label>
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  value={interviewMode}
                  onChange={(e) => setInterviewMode(e.target.value)}
                  placeholder="e.g. Virtual / Video, Walk-in"
                  className="w-full px-3 py-2.5 text-xs bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] transition"
                />
                <input
                  type="text"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  placeholder="e.g. Apply before 30th Nov"
                  className="w-full px-3 py-2.5 text-xs bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] transition"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#fbfbfa] uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-emerald-300" /> Stated Company Address / Location
            </label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="e.g. Electronic City, Bengaluru, Karnataka"
              className="w-full px-4 py-3 text-sm bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] placeholder:text-[rgba(251,251,250,0.4)] focus:outline-none focus:border-[#176247] focus:ring-1 focus:ring-[#176247] transition"
            />
          </div>

          {rawText && (
            <div className="pt-2">
              <div className="text-[11px] font-semibold text-[rgba(251,251,250,0.7)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-emerald-300" /> Source Document / Extracted Text Snippet
              </div>
              <div className="p-4 bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-xs font-mono text-[rgba(251,251,250,0.9)] max-h-36 overflow-y-auto leading-relaxed">
                {rawText}
              </div>
            </div>
          )}

          <div className="pt-4 border-t border-[rgba(251,251,250,0.15)] flex justify-end gap-3">
            <button
              type="button"
              onClick={() => navigate("/")}
              className="px-5 py-2.5 text-xs font-medium rounded-[10px] border border-[rgba(251,251,250,0.22)] text-[rgba(251,251,250,0.85)] hover:bg-[rgba(251,251,250,0.1)] transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleContinue}
              className="px-8 py-3 text-xs font-medium rounded-[10px] bg-[#142b22] text-[#fff] border border-[#10261d] hover:bg-[#204434] transition inline-flex items-center gap-2 shadow-[0_1px_2px_#10261d1a]"
            >
              Continue to Verification <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </main>

      {/* Footer - Full Screen Width */}
      <footer className="border-t border-[rgba(251,251,250,0.15)] bg-[rgba(8,45,34,0.85)] py-6 text-center text-xs text-[rgba(251,251,250,0.65)] mt-auto w-full">
        <div className="w-full max-w-[1500px] mx-auto px-4 sm:px-8 lg:px-12 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            FraudJobDetector • Independent Corporate Identity & Recruitment Due Diligence Engine
          </div>
          <div className="flex items-center gap-4 text-xs">
            <Link to="/privacy" className="text-[rgba(251,251,250,0.65)] hover:text-[#fff] transition">
              Privacy Policy
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

export default Review;
