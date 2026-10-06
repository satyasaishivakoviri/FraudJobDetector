import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { ImageGenerationLoader } from "@/components/ui/image-generation-loader";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
  Share2,
  ExternalLink,
  Building,
  Globe,
  FileText,
  CheckCircle2,
  Copy,
  Check,
  X,
  Clock,
  ArrowLeft,
  FileCheck2,
  Receipt,
  Lock,
  Shield
} from "lucide-react";

const GREEN_BG_STYLE: React.CSSProperties = {
  background: "#0b3b2a",
  backgroundImage:
    "radial-gradient(circle at 18% 8%, rgba(68,125,98,.72), transparent 34%), radial-gradient(circle at 82% 20%, rgba(251,251,250,.12), transparent 28%), radial-gradient(circle at 48% 78%, rgba(9,48,35,.5), transparent 44%), linear-gradient(135deg,#0b3b2a 0%,#14573f 48%,#082d22 100%)",
  minHeight: "100vh",
};

const getReasonText = (reason: any): string => {
  if (!reason) return "";
  if (typeof reason === "string") return reason;
  if (typeof reason === "object") {
    return String(reason.reason || reason.description || reason.message || reason.rule || JSON.stringify(reason));
  }
  return String(reason);
};

const getReasonScore = (reason: any): number | null => {
  if (typeof reason === "object" && reason !== null && typeof reason.score === "number") {
    return reason.score;
  }
  return null;
};

const getReasonRule = (reason: any): string | null => {
  if (typeof reason === "object" && reason !== null && reason.rule) {
    return String(reason.rule);
  }
  return null;
};

export const Results: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [loading, setLoading] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    const urlParams = new URLSearchParams(window.location.search);
    const hasToken = Boolean(urlParams.get("token") || urlParams.get("import_token"));
    const isPending = sessionStorage.getItem("fjd_pending_verification") === "true";
    return hasToken || isPending;
  });

  const [error, setError] = useState<string | null>(null);
  const [verificationResult, setVerificationResult] = useState<any | null>(() => {
    if (typeof window === "undefined") return null;
    const stored = sessionStorage.getItem("fjd_verification_results");
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch (e) {
        return null;
      }
    }
    return null;
  });

  const [recheckChanges, setRecheckChanges] = useState<any[] | null>(null);
  const [verificationUpdatedTime, setVerificationUpdatedTime] = useState<string | null>(null);

  const [shareModalOpen, setShareModalOpen] = useState<boolean>(false);
  const [shareUrl, setShareUrl] = useState<string>("");
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [revokeToken, setRevokeToken] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<boolean>(false);
  const [shareLoading, setShareLoading] = useState<boolean>(false);

  const isExecutingRef = useRef<boolean>(false);
  const executedRef = useRef<boolean>(false);

  const executeVerification = useCallback(async (payloadOverride?: any) => {
    if (isExecutingRef.current) return;
    isExecutingRef.current = true;

    setLoading(true);
    setError(null);

    try {
      let payload = payloadOverride;
      if (!payload) {
        const storedEdited = sessionStorage.getItem("fjd_edited_entities");
        let editedData: any = {};
        try {
          editedData = storedEdited ? JSON.parse(storedEdited) : {};
        } catch (e) {
          editedData = {};
        }

        const rawText = sessionStorage.getItem("fjd_raw_message") || "";
        const inputSource = sessionStorage.getItem("fjd_input_source") || "message";
        const storedOffer = sessionStorage.getItem("fjd_offer_letter_data");
        let offerData: any = null;
        try {
          offerData = storedOffer ? JSON.parse(storedOffer) : null;
        } catch (e) {
          offerData = null;
        }

        const compName = (editedData.company_name || "").trim();
        if (!compName) {
          navigate("/review");
          return;
        }
        const domain = editedData.claimed_domain || editedData.company_domain || editedData.domain_or_url || null;
        const gstin = editedData.gstin || null;
        const email = editedData.contact_email || editedData.recruiter_email || editedData.email_address || null;

        payload = {
          company_name: compName,
          claimed_domain: domain,
          gstin: gstin,
          contact_email: email,
          job_message: rawText || null,
          description: rawText || null,
          offer_data: offerData,
          input_source: inputSource,
        };
      }

      const res = await fetch("/check-company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Verification failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      sessionStorage.setItem("fjd_verification_results", JSON.stringify(data));
      sessionStorage.removeItem("fjd_pending_verification");
      setVerificationResult(data);
    } catch (err: any) {
      sessionStorage.removeItem("fjd_pending_verification");
      setError(err?.message || "Failed to complete verification. Please check network connection.");
    } finally {
      setLoading(false);
      isExecutingRef.current = false;
    }
  }, []);

  useEffect(() => {
    const token = searchParams.get("token") || searchParams.get("import_token");

    if (token) {
      if (executedRef.current) return;
      executedRef.current = true;
      setLoading(true);
      setError(null);
      fetch(`/api/report/${encodeURIComponent(token)}`)
        .then((res) => {
          if (!res.ok) throw new Error(`Could not load report (HTTP ${res.status})`);
          return res.json();
        })
        .then((data) => {
          setVerificationResult(data);
          sessionStorage.setItem("fjd_verification_results", JSON.stringify(data));
        })
        .catch((err) => {
          setError(err.message || "Failed to load shared verification report.");
        })
        .finally(() => {
          setLoading(false);
        });
      return;
    }

    const pending = sessionStorage.getItem("fjd_pending_verification");
    if (pending === "true") {
      if (executedRef.current) return;
      executedRef.current = true;
      executeVerification();
      return;
    }

    const stored = sessionStorage.getItem("fjd_verification_results");
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setVerificationResult(parsed);
      } catch (e) {
        navigate("/");
      }
      return;
    }

    if (!loading && !isExecutingRef.current && !executedRef.current) {
      navigate("/");
    }
  }, [searchParams, executeVerification, navigate, loading]);

  const handleRecheck = async () => {
    if (loading || isExecutingRef.current) return;
    isExecutingRef.current = true;

    setLoading(true);
    setError(null);

    const storedEdited = sessionStorage.getItem("fjd_edited_entities");
    let editedData: any = {};
    try {
      editedData = storedEdited ? JSON.parse(storedEdited) : {};
    } catch (e) {}

    const compName =
      editedData.company_name ||
      (typeof verificationResult?.company_identity === "object"
        ? verificationResult?.company_identity?.company_name
        : verificationResult?.company_identity) ||
      "Company";
    const domain = editedData.claimed_domain || verificationResult?.domain?.domain || null;
    const gstin = editedData.gstin || verificationResult?.gst?.gstin || null;
    const email = editedData.contact_email || null;
    const rawText = sessionStorage.getItem("fjd_raw_message") || null;
    const storedOffer = sessionStorage.getItem("fjd_offer_letter_data");
    let offerData: any = null;
    try {
      offerData = storedOffer ? JSON.parse(storedOffer) : null;
    } catch (e) {}

    const payload = {
      company_name: compName,
      claimed_domain: domain,
      gstin: gstin,
      contact_email: email,
      job_message: rawText,
      description: rawText,
      offer_data: offerData,
      previous_result: verificationResult,
      input_source: "recheck",
    };

    try {
      const res = await fetch("/recheck-company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Recheck failed with HTTP ${res.status}`);
      }

      const freshData = await res.json();
      sessionStorage.setItem("fjd_verification_results", JSON.stringify(freshData));
      setVerificationResult(freshData);
      setVerificationUpdatedTime(freshData.verified_at || new Date().toLocaleString());
      if (freshData.verification_changes && freshData.verification_changes.length > 0) {
        setRecheckChanges(freshData.verification_changes);
      }
    } catch (err: any) {
      setError("Recheck notice: " + (err?.message || "Failed to re-verify employer records."));
    } finally {
      setLoading(false);
      isExecutingRef.current = false;
    }
  };

  const handleOpenShareModal = async () => {
    if (!verificationResult) return;
    setShareModalOpen(true);
    setShareLoading(true);
    setShareUrl("Generating secure share link...");

    try {
      const resp = await fetch("/create-share-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          verification_id: verificationResult.verification_id,
          report_data: verificationResult,
        }),
      });

      if (!resp.ok) throw new Error("Failed to create temporary share link.");
      const data = await resp.json();
      setShareToken(data.report_token);
      setRevokeToken(data.revoke_token);
      const fullUrl = `${window.location.origin}${data.share_url}`;
      setShareUrl(fullUrl);
    } catch (err: any) {
      setShareUrl("Error generating link: " + err.message);
    } finally {
      setShareLoading(false);
    }
  };

  const handleCopyLink = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2500);
    } catch (e) {
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2500);
    }
  };

  const handleRevokeShare = async () => {
    if (!shareToken || !revokeToken) return;
    if (!window.confirm("Permanently revoke this public report link? It will stop working immediately.")) return;

    try {
      const resp = await fetch(`/report/${encodeURIComponent(shareToken)}/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ revoke_token: revokeToken }),
      });

      if (resp.ok) {
        alert("Public report link revoked.");
        setShareModalOpen(false);
        setShareToken(null);
        setRevokeToken(null);
      } else {
        alert("Could not revoke link.");
      }
    } catch (e: any) {
      alert("Revoke failed: " + e.message);
    }
  };

  const riskLevel = String(verificationResult?.risk_level || "low").toLowerCase();
  const riskScore = verificationResult?.risk_score !== undefined ? verificationResult.risk_score : 0;
  const companyName =
    (typeof verificationResult?.company_identity === "object"
      ? verificationResult?.company_identity?.company_name
      : verificationResult?.company_identity) ||
    verificationResult?.company_name ||
    verificationResult?.investigated_company ||
    "Company Under Investigation";

  return (
    <div style={GREEN_BG_STYLE} className="text-[#fbfbfa] flex flex-col font-sans">
      {/* Header */}
      <header className="bg-[#0b3b2a]/80 backdrop-blur-md border-b border-[rgba(251,251,250,0.15)] py-3.5 px-4 sm:px-8 lg:px-12 sticky top-0 z-30 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
        <div className="max-w-[1500px] mx-auto flex items-center justify-between">
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
              onClick={() => {
                sessionStorage.clear();
                navigate("/");
              }}
              className="text-xs font-medium px-3.5 py-1.5 rounded-[10px] bg-[#142b22] text-[#fbfbfa] border border-[#10261d] hover:bg-[#204434] transition inline-flex items-center gap-1.5 shadow-xs"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              New Scan
            </button>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 max-w-[1500px] w-full mx-auto px-4 sm:px-8 lg:px-12 py-8 sm:py-10">
        {loading || (!verificationResult && !error) ? (
          <div className="py-16 sm:py-24 flex flex-col items-center justify-center">
            <ImageGenerationLoader
              effect="scale-wave"
              easing="ease-in-out"
              text="Analyzing Job Offer"
              cellSize={3}
              gap={1}
              bandHeight={48}
              colors={["#34d399", "#0b3b2a"]}
              subMessages={[
                "Querying MCA corporate registrations",
                "Auditing GSTN taxpayer status",
                "Verifying domain WHOIS and mail servers",
                "Evaluating multi-factor risk rules",
              ]}
              subMessageInterval={1800}
            />
          </div>
        ) : error && !verificationResult ? (
          <div className="max-w-xl mx-auto my-12 bg-[rgba(11,59,42,0.7)] backdrop-blur-md rounded-xl border border-red-500/40 p-8 shadow-[0_4px_16px_rgba(0,0,0,0.2)] text-center">
            <div className="w-14 h-14 rounded-xl bg-red-950/60 text-red-400 flex items-center justify-center mx-auto mb-4 border border-red-800/40">
              <ShieldAlert className="w-7 h-7" />
            </div>
            <h2 className="text-xl font-bold text-[#fbfbfa] mb-2">Verification Incomplete</h2>
            <p className="text-xs text-[rgba(251,251,250,0.75)] mb-6 leading-relaxed">{error}</p>
            <div className="flex justify-center gap-3">
              <button
                onClick={() => navigate("/review")}
                className="px-4 py-2.5 text-xs font-medium rounded-[10px] border border-[rgba(251,251,250,0.22)] text-[rgba(251,251,250,0.85)] hover:bg-[rgba(251,251,250,0.1)] transition"
              >
                Back to Review
              </button>
              <button
                onClick={() => executeVerification()}
                className="px-5 py-2.5 text-xs font-medium rounded-[10px] bg-[#142b22] text-white hover:bg-[#204434] transition shadow-[0_1px_2px_#10261d1a] inline-flex items-center gap-2 border border-[#10261d]"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Retry Verification
              </button>
            </div>
          </div>
        ) : verificationResult ? (
          <div className="space-y-6">
            {/* Notice banner */}
            {error && (
              <div className="bg-amber-950/60 border border-amber-600/40 text-amber-200 rounded-xl px-4 py-3 flex items-start gap-3 text-xs">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <strong>Notice:</strong> {error}
                  <div className="text-[11px] text-amber-300/80 mt-0.5">
                    Previous verified findings are preserved below.
                  </div>
                </div>
                <button
                  onClick={() => setError(null)}
                  className="text-amber-400 hover:text-amber-200"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Recheck Updated Notice */}
            {verificationUpdatedTime && (
              <div className="bg-[rgba(8,45,34,0.7)] border border-emerald-500/40 text-emerald-200 rounded-xl px-4 py-3 flex items-center gap-2 text-xs font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-300" />
                <span>Verification updated • Checked: {verificationUpdatedTime}</span>
              </div>
            )}

            {/* Recheck Differences Card */}
            {recheckChanges && recheckChanges.length > 0 && (
              <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md border border-[rgba(251,251,250,0.22)] rounded-xl p-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#fbfbfa] mb-2 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-emerald-300" /> Changes Detected Since Last Check
                </h4>
                <div className="space-y-2">
                  {recheckChanges.map((ch: any, idx: number) => (
                    <div key={idx} className="text-xs bg-[#082d22] p-2.5 rounded-lg border border-[rgba(251,251,250,0.15)]">
                      <span className="font-semibold text-[#fbfbfa]">{String(ch.field || "Field")}:</span> Changed from{" "}
                      <span className="italic text-[rgba(251,251,250,0.6)]">
                        {typeof ch.previous === "object" ? JSON.stringify(ch.previous) : String(ch.previous ?? "")}
                      </span>{" "}
                      to{" "}
                      <span className="font-semibold text-emerald-300">
                        {typeof ch.current === "object" ? JSON.stringify(ch.current) : String(ch.current ?? "")}
                      </span>
                      {ch.message && <p className="text-[rgba(251,251,250,0.7)] mt-0.5">{String(ch.message)}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Report Header Card */}
            <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)] flex flex-col md:flex-row md:items-center justify-between gap-5">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-md bg-[#082d22] text-[#fbfbfa] border border-[rgba(251,251,250,0.22)]">
                    {verificationResult.verification_id || "VER-2026-00000"}
                  </span>
                  <span className="text-xs text-[rgba(251,251,250,0.7)]">
                    Verified {verificationResult.verified_at || new Date().toLocaleDateString()}
                  </span>
                </div>
                <h1 className="text-2xl sm:text-3xl font-bold text-[#fbfbfa] tracking-tight">
                  {companyName}
                </h1>
                <p className="text-xs text-[rgba(251,251,250,0.7)] mt-1">
                  Independent Statutory & Operational Corporate Identity Verification
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2.5">
                <button
                  type="button"
                  id="btnRecheck"
                  disabled={loading}
                  onClick={handleRecheck}
                  className="px-4 py-2 text-xs font-medium rounded-[10px] border border-[rgba(251,251,250,0.22)] bg-[#082d22] text-[#fbfbfa] hover:bg-[#142b22] transition inline-flex items-center gap-1.5 shadow-xs disabled:opacity-50"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Recheck Verification
                </button>

                <button
                  type="button"
                  id="btnShareReport"
                  onClick={handleOpenShareModal}
                  className="px-4 py-2 text-xs font-medium rounded-[10px] bg-[#142b22] text-white border border-[#10261d] hover:bg-[#204434] transition inline-flex items-center gap-1.5 shadow-[0_1px_2px_#10261d1a]"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  Share Report
                </button>
              </div>
            </div>

            {/* Risk Assessment Panel */}
            <div
              className={`rounded-xl border p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)] ${
                riskLevel === "high"
                  ? "bg-[rgba(127,29,29,0.3)] border-red-500/40 text-red-100"
                  : riskLevel === "medium"
                  ? "bg-[rgba(180,83,9,0.3)] border-amber-500/40 text-amber-100"
                  : "bg-[rgba(11,59,42,0.8)] border-emerald-500/40 text-[#fbfbfa]"
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md ${
                        riskLevel === "high"
                          ? "bg-red-700 text-white"
                          : riskLevel === "medium"
                          ? "bg-amber-600 text-white"
                          : "bg-[#142b22] border border-[rgba(251,251,250,0.3)] text-white"
                      }`}
                    >
                      {riskLevel} Risk
                    </span>
                    <span className="text-xs font-semibold text-[rgba(251,251,250,0.7)]">
                      Multi-Factor Statutory Heuristic Engine
                    </span>
                  </div>
                  <h3 className="text-xl font-bold text-[#fbfbfa]">
                    {riskLevel === "high"
                      ? "High Risk Indicators Detected"
                      : riskLevel === "medium"
                      ? "Suspicious Patterns Require Caution"
                      : "Low Risk Profile Corroborated"}
                  </h3>
                  <p className="text-xs sm:text-sm text-[rgba(251,251,250,0.85)] max-w-xl leading-relaxed">
                    {riskLevel === "high"
                      ? "Multiple critical red flags identified. High likelihood of recruitment impersonation or fee extortion fraud."
                      : riskLevel === "medium"
                      ? "Discrepancies found between stated identity and verified registries. Proceed with careful verification."
                      : "Company credentials corroborate registered business registries. Always follow safe recruitment practices."}
                  </p>
                </div>

                {/* Score Dial */}
                <div className="flex items-center gap-4 bg-[#082d22] p-4 rounded-xl border border-[rgba(251,251,250,0.22)] shadow-xs shrink-0">
                  <div className="text-right">
                    <div className="text-[10px] font-bold text-[rgba(251,251,250,0.65)] uppercase tracking-wider">
                      Fraud Risk Score
                    </div>
                    <div
                      className={`text-3xl font-extrabold ${
                        riskLevel === "high"
                          ? "text-red-400"
                          : riskLevel === "medium"
                          ? "text-amber-400"
                          : "text-emerald-300"
                      }`}
                    >
                      {riskScore}
                      <span className="text-sm font-medium text-[rgba(251,251,250,0.5)]">/100</span>
                    </div>
                  </div>
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-[#142b22] border border-[rgba(251,251,250,0.2)]">
                    {riskLevel === "high" ? (
                      <ShieldAlert className="w-6 h-6 text-red-400" />
                    ) : riskLevel === "medium" ? (
                      <AlertTriangle className="w-6 h-6 text-amber-400" />
                    ) : (
                      <ShieldCheck className="w-6 h-6 text-emerald-300" />
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Risk Signals Grid */}
            {verificationResult.reasons && verificationResult.reasons.length > 0 && (
              <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[rgba(251,251,250,0.7)] mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Detected Risk Signals & Discrepancies
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {verificationResult.reasons.map((reasonItem: any, idx: number) => {
                    const reasonText = getReasonText(reasonItem);
                    const ruleName = getReasonRule(reasonItem);
                    const score = getReasonScore(reasonItem);

                    return (
                      <div
                        key={idx}
                        className="p-3.5 rounded-lg bg-[#082d22] border border-[rgba(251,251,250,0.18)] flex items-start gap-3 text-xs text-[#fbfbfa] hover:border-[rgba(251,251,250,0.35)] transition"
                      >
                        <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0 mt-1.5 shadow-xs" />
                        <div className="flex-1">
                          {ruleName && (
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[10px] font-mono font-semibold text-[rgba(251,251,250,0.6)] uppercase tracking-wider">
                                {ruleName}
                              </span>
                              {score !== null && score > 0 && (
                                <span className="text-[10px] font-bold text-amber-200 bg-amber-950/70 px-1.5 py-0.5 rounded border border-amber-800/60">
                                  +{score} pts
                                </span>
                              )}
                            </div>
                          )}
                          <span className="font-normal leading-relaxed text-[rgba(251,251,250,0.95)]">{reasonText}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Statutory Verification Findings & Evidence */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* MCA Corporate Registration */}
              <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 shadow-[0_4px_16px_rgba(0,0,0,0.15)] space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[rgba(251,251,250,0.12)]">
                  <div className="flex items-center gap-2 font-bold text-sm text-[#fbfbfa]">
                    <Building className="w-4 h-4 text-emerald-300" />
                    MCA Registry Verification
                  </div>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                      String(verificationResult?.mca?.status || "").toLowerCase() === "active"
                        ? "bg-[#142b22] text-emerald-300 border border-emerald-500/40"
                        : "bg-[#082d22] text-[rgba(251,251,250,0.65)] border border-[rgba(251,251,250,0.2)]"
                    }`}
                  >
                    {String(verificationResult?.mca?.status || "Not Available")}
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">CIN:</span>
                    <span className="font-mono font-semibold text-[#fbfbfa]">
                      {String(verificationResult?.mca?.cin || "Not Available")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">Class / Category:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {String(verificationResult?.mca?.class || verificationResult?.mca?.company_class || "Not Available")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[rgba(251,251,250,0.65)]">ROC Office:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {String(verificationResult?.mca?.roc || "Not Available")}
                    </span>
                  </div>
                </div>
                <div className="pt-2">
                  <a
                    href="https://www.mca.gov.in/content/mca21/en/services/master-data/company-llp-info.html"
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-semibold text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1 transition"
                  >
                    Verify on MCA Portal <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {/* GST Taxpayer Verification */}
              <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 shadow-[0_4px_16px_rgba(0,0,0,0.15)] space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[rgba(251,251,250,0.12)]">
                  <div className="flex items-center gap-2 font-bold text-sm text-[#fbfbfa]">
                    <Receipt className="w-4 h-4 text-emerald-300" />
                    GST Taxpayer Verification
                  </div>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                      String(verificationResult?.gst?.status || "").toLowerCase() === "active"
                        ? "bg-[#142b22] text-emerald-300 border border-emerald-500/40"
                        : "bg-[#082d22] text-[rgba(251,251,250,0.65)] border border-[rgba(251,251,250,0.2)]"
                    }`}
                  >
                    {String(verificationResult?.gst?.status || "Not Available")}
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">GSTIN:</span>
                    <span className="font-mono font-semibold text-[#fbfbfa]">
                      {String(verificationResult?.gst?.gstin || "Not Available")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">Legal Name:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {String(verificationResult?.gst?.legal_name || verificationResult?.gst?.trade_name || "Not Available")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[rgba(251,251,250,0.65)]">Jurisdiction:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {String(verificationResult?.gst?.state || verificationResult?.gst?.state_jurisdiction || "Not Available")}
                    </span>
                  </div>
                </div>
                <div className="pt-2">
                  <a
                    href="https://services.gst.gov.in/services/searchtp"
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-semibold text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1 transition"
                  >
                    Verify on GST Portal <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {/* Udyam MSME Registration */}
              <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 shadow-[0_4px_16px_rgba(0,0,0,0.15)] space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[rgba(251,251,250,0.12)]">
                  <div className="flex items-center gap-2 font-bold text-sm text-[#fbfbfa]">
                    <FileText className="w-4 h-4 text-emerald-300" />
                    Udyam MSME Registry
                  </div>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                      verificationResult?.udyam?.registered
                        ? "bg-[#142b22] text-emerald-300 border border-emerald-500/40"
                        : "bg-[#082d22] text-[rgba(251,251,250,0.65)] border border-[rgba(251,251,250,0.2)]"
                    }`}
                  >
                    {verificationResult?.udyam?.registered ? "Registered" : "Not Registered"}
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">Udyam Reg No:</span>
                    <span className="font-mono font-semibold text-[#fbfbfa]">
                      {String(verificationResult?.udyam?.udyam_number || "Not Available")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">Enterprise Name:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {String(verificationResult?.udyam?.enterprise_name || "Not Available")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[rgba(251,251,250,0.65)]">Major Activity:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {String(verificationResult?.udyam?.major_activity || "Not Available")}
                    </span>
                  </div>
                </div>
                <div className="pt-2">
                  <a
                    href="https://udyamregistration.gov.in/Udyam_Verify.aspx"
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-semibold text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1 transition"
                  >
                    Verify on Udyam Portal <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {/* Domain & Digital Footprint */}
              <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 shadow-[0_4px_16px_rgba(0,0,0,0.15)] space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[rgba(251,251,250,0.12)]">
                  <div className="flex items-center gap-2 font-bold text-sm text-[#fbfbfa]">
                    <Globe className="w-4 h-4 text-emerald-300" />
                    Domain & Digital Footprint
                  </div>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                      verificationResult?.domain?.ssl_valid
                        ? "bg-[#142b22] text-emerald-300 border border-emerald-500/40"
                        : "bg-amber-950/60 text-amber-300 border border-amber-700/50"
                    }`}
                  >
                    {verificationResult?.domain?.ssl_valid ? "SSL Valid" : "No SSL / Unverified"}
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">Claimed Domain:</span>
                    <span className="font-mono font-semibold text-[#fbfbfa]">
                      {String(verificationResult?.domain?.domain || "Not Available")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[rgba(251,251,250,0.06)]">
                    <span className="text-[rgba(251,251,250,0.65)]">Domain Age:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {verificationResult?.domain?.age_days
                        ? `${verificationResult.domain.age_days} days`
                        : "Not Available"}
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[rgba(251,251,250,0.65)]">Recruiter Email Provider:</span>
                    <span className="font-medium text-[#fbfbfa]">
                      {verificationResult?.email?.is_free_provider ? "Public / Free (High Risk)" : "Corporate Domain"}
                    </span>
                  </div>
                </div>
                <div className="pt-2">
                  <a
                    href={`https://who.is/whois/${verificationResult?.domain?.domain || ""}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-semibold text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1 transition"
                  >
                    View Domain WHOIS <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            </div>

            {/* Offer Letter Consistency Cross-Examination */}
            {verificationResult.offer_letter_consistency &&
              Array.isArray(verificationResult.offer_letter_consistency) &&
              verificationResult.offer_letter_consistency.length > 0 && (
                <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
                  <div className="mb-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5">
                      <FileCheck2 className="w-4 h-4 text-emerald-300" /> Offer Document Cross-Examination
                    </div>
                    <h3 className="text-base font-bold text-[#fbfbfa] mt-1">
                      Consistency Findings & Verification Claims
                    </h3>
                    <p className="text-xs text-[rgba(251,251,250,0.7)]">
                      Cross-referenced against verified government corporate registrations.
                    </p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left border-collapse">
                      <thead>
                        <tr className="border-b border-[rgba(251,251,250,0.15)] bg-[#082d22] text-[#fbfbfa] uppercase text-[10px] tracking-wider font-semibold">
                          <th className="py-2.5 px-3">Field</th>
                          <th className="py-2.5 px-3">Claimed in Offer</th>
                          <th className="py-2.5 px-3">Verified Official Finding</th>
                          <th className="py-2.5 px-3">Verdict</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[rgba(251,251,250,0.08)]">
                        {verificationResult.offer_letter_consistency.map((item: any, idx: number) => {
                          const status = String(item.status || "").toUpperCase();
                          return (
                            <tr key={idx} className="hover:bg-[rgba(251,251,250,0.04)]">
                              <td className="py-2.5 px-3 font-semibold text-[#fbfbfa]">
                                {String(item.parameter || item.field || "-")}
                              </td>
                              <td className="py-2.5 px-3 text-[rgba(251,251,250,0.8)]">
                                {String(item.claimed_in_offer || item.claimed || "-")}
                              </td>
                              <td className="py-2.5 px-3 text-emerald-200 font-medium">
                                {String(item.verified_in_registry || item.verified || "-")}
                              </td>
                              <td className="py-2.5 px-3">
                                <span
                                  className={`px-2 py-0.5 rounded-md text-[10px] font-semibold ${
                                    status === "MATCH" || status === "VERIFIED"
                                      ? "bg-[#142b22] text-emerald-300 border border-emerald-500/40"
                                      : status === "DISCREPANCY" || status === "MISMATCH"
                                      ? "bg-red-950/70 text-red-200 border border-red-800/60"
                                      : "bg-[#082d22] text-[rgba(251,251,250,0.65)] border border-[rgba(251,251,250,0.2)]"
                                  }`}
                                >
                                  {item.status || "UNVERIFIED"}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

            {/* Dynamic Safety Recommendations Section */}
            <div className="bg-[rgba(11,59,42,0.65)] backdrop-blur-md rounded-xl border border-[rgba(251,251,250,0.22)] p-6 sm:p-7 shadow-[0_4px_16px_rgba(0,0,0,0.15)]">
              <div className="flex items-center gap-2 mb-1.5">
                <ShieldCheck className="w-5 h-5 text-emerald-300" />
                <h3 className="text-base font-bold text-[#fbfbfa]">Actionable Due Diligence Recommendations</h3>
              </div>
              <p className="text-xs text-[rgba(251,251,250,0.7)] mb-5">
                {riskLevel === "high"
                  ? "Take the following mandatory precautions before interacting further with this offer."
                  : "Follow standard corporate diligence procedures before providing documents or commitments."}
              </p>

              <div className="space-y-3">
                {verificationResult.safety_recommendations &&
                verificationResult.safety_recommendations.length > 0 ? (
                  verificationResult.safety_recommendations.map((rec: any, idx: number) => {
                    const isObj = typeof rec === "object" && rec !== null;
                    const title = isObj
                      ? String(rec.title || rec.type || `Recommendation ${idx + 1}`)
                      : `Recommendation ${idx + 1}`;
                    const msg = isObj
                      ? String(rec.message || rec.description || rec.text || JSON.stringify(rec))
                      : String(rec);
                    const priority = isObj ? String(rec.priority || "medium") : "medium";

                    return (
                      <div
                        key={idx}
                        className="bg-[#082d22] p-4 rounded-xl border border-[rgba(251,251,250,0.18)] flex items-start gap-3.5"
                      >
                        <span
                          className={`w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold shrink-0 ${
                            priority === "high"
                              ? "bg-red-700 text-white"
                              : "bg-[#142b22] border border-[rgba(251,251,250,0.3)] text-white"
                          }`}
                        >
                          {idx + 1}
                        </span>
                        <div className="flex-1 text-xs">
                          <div className="font-semibold text-[#fbfbfa] flex items-center gap-2">
                            {title}
                            {priority === "high" && (
                              <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-red-900/80 text-red-200 border border-red-700/50">
                                High Priority
                              </span>
                            )}
                          </div>
                          <div className="text-[rgba(251,251,250,0.8)] mt-1 leading-relaxed">{msg}</div>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-xs text-[rgba(251,251,250,0.7)]">
                    Verify the employer using its official website and independently confirm recruiter credentials.
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </main>

      {/* Share Report Modal */}
      {shareModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#0b3b2a] rounded-xl max-w-md w-full border border-[rgba(251,251,250,0.25)] shadow-2xl overflow-hidden text-[#fbfbfa]">
            <div className="p-5 border-b border-[rgba(251,251,250,0.15)] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Share2 className="w-4 h-4 text-emerald-300" />
                <h3 className="font-bold text-[#fbfbfa] text-sm">Temporary Shareable Report</h3>
              </div>
              <button
                onClick={() => setShareModalOpen(false)}
                className="text-[rgba(251,251,250,0.6)] hover:text-[#fff]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="text-xs font-semibold text-[rgba(251,251,250,0.7)] uppercase tracking-wider block mb-1.5">
                  Public Share Link
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    readOnly
                    value={shareUrl}
                    className="flex-1 px-3 py-2 text-xs font-mono bg-[#082d22] border border-[rgba(251,251,250,0.22)] rounded-lg text-[#fbfbfa] focus:outline-none"
                  />
                  <button
                    onClick={handleCopyLink}
                    disabled={shareLoading}
                    className="px-3.5 py-2 text-xs font-medium rounded-[10px] bg-[#142b22] text-white hover:bg-[#204434] transition inline-flex items-center gap-1.5 shrink-0 shadow-[0_1px_2px_#10261d1a] border border-[#10261d]"
                  >
                    {copyFeedback ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    {copyFeedback ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>

              <div className="bg-[rgba(8,45,34,0.7)] border border-[rgba(251,251,250,0.2)] p-3.5 rounded-xl text-xs text-emerald-200 flex items-start gap-2.5">
                <Lock className="w-4 h-4 shrink-0 mt-0.5 text-emerald-300" />
                <div>
                  <strong>Privacy Protected:</strong> All candidate personal data, contact numbers, and raw documents are stripped. Only vetted corporate evidence is shared.
                </div>
              </div>

              <div className="text-[11px] text-[rgba(251,251,250,0.65)] flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-emerald-300" />
                This temporary link automatically expires in <strong>7 days</strong>.
              </div>

              <div className="pt-3 border-t border-[rgba(251,251,250,0.15)] flex justify-between items-center">
                <button
                  onClick={handleRevokeShare}
                  className="text-xs font-medium text-red-300 hover:text-red-100 px-2 py-1 rounded hover:bg-red-950/60"
                >
                  Revoke Link Now
                </button>
                <button
                  onClick={() => setShareModalOpen(false)}
                  className="px-4 py-1.5 text-xs font-medium bg-[#142b22] text-[#fbfbfa] border border-[rgba(251,251,250,0.2)] rounded-[10px] hover:bg-[#204434] transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-[rgba(251,251,250,0.15)] bg-[rgba(8,45,34,0.85)] py-6 text-center text-xs text-[rgba(251,251,250,0.65)] mt-auto">
        <div className="max-w-[1500px] mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
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

export default Results;
