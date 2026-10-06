"use client";

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import GlyphPortal from "@/components/ui/glyph-portal";
import {
  FileText,
  FileUp,
  Image as ImageIcon,
  ArrowRight,
  AlertCircle,
  Search
} from "lucide-react";

const settings = {
  word: "FRAUD",
  scrollLength: 2.4,
  interactive: true,
  annotations: false
};

const family = '"Glyph Portal Jakarta", Arial, sans-serif';
let fontLoad: Promise<void> | undefined;

export default function Demo(props: Partial<typeof settings>) {
  const s = { ...settings, ...props };
  const navigate = useNavigate();
  const [face, setFace] = useState<string | null>(null);

  // Form submission state for revealed section
  const [activeTab, setActiveTab] = useState<"text" | "offer" | "screenshot">("text");
  const [jobMessage, setJobMessage] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let settled = false;
    const finish = (value: string) => {
      if (!settled) {
        settled = true;
        setFace(value);
      }
    };
    // The demo uses the résumé's face. The component itself never fetches a font.
    fontLoad ??= new FontFace(
      "Glyph Portal Jakarta",
      'url("https://cdn.21st.dev/assets/mirror/15/153fc85b70298beeb1d61a5f723331649e7f23bb77302a66e61cb3e2fbdb5e79.woff2")',
      { weight: "400 700" }
    )
      .load()
      .then((font) => {
        document.fonts.add(font);
      });
    const timeout = window.setTimeout(() => finish("Arial, sans-serif"), 1600);
    void fontLoad.then(
      () => finish(family),
      () => finish("Arial, sans-serif")
    );
    return () => {
      settled = true;
      clearTimeout(timeout);
    };
  }, []);

  const handleAnalyzeJob = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!jobMessage.trim()) {
      setError("Please paste a suspicious job posting, recruitment email, or offer message.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/extract-entities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: jobMessage, message: jobMessage }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Could not extract entities (HTTP ${res.status})`);
      }
      const entities = await res.json();

      sessionStorage.setItem("fjd_raw_message", jobMessage);
      sessionStorage.setItem("fjd_input_source", "message");
      sessionStorage.setItem("fjd_extracted_entities", JSON.stringify(entities));
      sessionStorage.setItem("fjd_edited_entities", JSON.stringify(entities));
      sessionStorage.removeItem("fjd_screenshot_preview");
      sessionStorage.removeItem("fjd_offer_letter_data");
      sessionStorage.removeItem("fjd_screenshot_signals");

      navigate("/review");
    } catch (err: any) {
      setError(err?.message || "Failed to analyze job message. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a document or screenshot file.");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    const endpoint = activeTab === "offer" ? "/upload/offer-letter" : "/upload/screenshot";
    formData.append("file", file);

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      const rawText = data.raw_text || data.extracted_text || "";
      sessionStorage.setItem("fjd_input_source", activeTab === "offer" ? "offer_letter" : "screenshot");
      sessionStorage.setItem("fjd_raw_message", rawText);

      if (activeTab === "offer") {
        const offerData = data.extracted_data || data.offer_data || {};
        sessionStorage.setItem("fjd_offer_letter_data", JSON.stringify(offerData));
        sessionStorage.setItem("fjd_extracted_entities", JSON.stringify(offerData));
        sessionStorage.setItem("fjd_edited_entities", JSON.stringify(offerData));
        sessionStorage.setItem("fjd_ocr_confidence", String(data.confidence || 0.95));
        sessionStorage.setItem("fjd_has_sensitive_info", data.has_sensitive_info ? "true" : "false");
        sessionStorage.removeItem("fjd_screenshot_preview");
        sessionStorage.removeItem("fjd_screenshot_signals");
      } else {
        const extracted = data.extracted_entities || {};
        sessionStorage.setItem("fjd_screenshot_signals", JSON.stringify(data.message_signals || []));
        sessionStorage.setItem("fjd_extracted_entities", JSON.stringify(extracted));
        sessionStorage.setItem("fjd_edited_entities", JSON.stringify(extracted));
        sessionStorage.setItem("fjd_screenshot_preview", data.image_preview_url || "");
        sessionStorage.setItem("fjd_ocr_confidence", String(data.confidence || 0.0));
        sessionStorage.setItem("fjd_low_confidence", data.low_confidence ? "true" : "false");
        sessionStorage.removeItem("fjd_offer_letter_data");
      }

      navigate("/review");
    } catch (err: any) {
      setError(err?.message || "File processing error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      data-demo-scroll
      data-slipstream-demo
      tabIndex={0}
      role="region"
      aria-label="FraudJobDetector. Scroll to step inside."
      style={{
        width: "100%",
        minHeight: "100vh",
        background: "#fff",
        containerType: "inline-size",
        fontFamily: face ?? "Arial, sans-serif",
      }}
    >
      <style>{`
        [data-slipstream-demo] [data-gp-caption]{inset:calc(var(--gp-word-bottom,50%) + 82px) 24px auto;justify-content:center;}
        [data-slipstream-demo] [data-gp-hint]{display:none;}
        [data-slipstream-demo] [data-gp-enter]{min-height:46px;padding:0 20px;gap:28px;background:#142b22;border:1px solid #10261d;border-radius:10px;color:#fff;font-size:13px;font-weight:500;box-shadow:0 1px 2px #10261d1a;transition:background .18s,box-shadow .18s;}
        [data-slipstream-demo] [data-gp-enter]:hover{background:#204434;box-shadow:0 3px 8px #10261d18;}
        [data-slipstream-demo] [data-gp-enter]:focus-visible{outline:2px solid #176247;outline-offset:4px;}
        [data-slipstream-demo] [data-gp-touch-picker]{top:auto;bottom:18px;left:50%;}
        [data-slipstream-demo] [data-gp-select]{border-color:transparent;border-radius:8px;font-size:12px;color:#626964;}
        [data-sublime-header]{position:absolute;inset:clamp(24px,4.5cqw,48px) clamp(24px,5cqw,64px) auto;display:flex;align-items:center;justify-content:space-between;gap:20px;}
        [data-sublime-logo]{font-size:19px;font-weight:600;letter-spacing:-.065em;color:#18251e;}
        [data-sublime-category]{font-size:12px;line-height:1.5;color:#71766f;}
        [data-sublime-eyebrow]{position:absolute;inset:auto 24px calc(100% - var(--gp-word-top,35%) + 32px);margin:0;text-align:center;font-size:13px;font-weight:400;line-height:1.5;letter-spacing:.005em;color:#71766f;}
        [data-sublime-support]{position:absolute;inset:calc(var(--gp-word-bottom,50%) + 32px) 24px auto;margin:0;text-align:center;font-size:16px;font-weight:400;line-height:1.5;color:#646a63;}
        [data-sublime-scroll]{position:absolute;inset:auto 24px 7%;text-align:center;color:#7c817b;font-size:11px;letter-spacing:.01em;}
        @media(any-pointer:coarse){[data-sublime-scroll]{bottom:13%;}}
        @container(max-width:450px){[data-sublime-category]{max-width:12ch;text-align:right;}[data-sublime-eyebrow]{font-size:12px;}[data-sublime-support]{font-size:14px;}[data-slipstream-demo] [data-gp-caption]{top:calc(var(--gp-word-bottom,50%) + 76px);}}
        @container(max-height:479px){[data-sublime-header]{top:18px;}[data-sublime-support]{top:calc(var(--gp-word-bottom,50%) + 16px);}[data-slipstream-demo] [data-gp-caption]{top:calc(var(--gp-word-bottom,50%) + 60px);}[data-sublime-scroll]{display:none;}}
        [data-slipstream-demo] [data-gp-content]{padding:5.5rem clamp(1.25rem,5cqw,5rem) 6.5rem;font-family:inherit;}
        [data-slipstream-demo] section,[data-slipstream-demo] [data-gp-caption]{font-family:inherit;}
        [data-slipstream-copy]{display:flex;width:min(100%,80rem);margin:auto;flex-direction:column;align-items:flex-start;gap:clamp(2rem,5svh,3.5rem);}
        [data-slipstream-copy] h2{max-width:48rem;margin:0;color:inherit;font-size:clamp(1.75rem,1.1rem + 2.1cqw,2.25rem);font-weight:400;line-height:1.25;letter-spacing:0;text-wrap:balance;}
        [data-slipstream-features]{display:grid;width:100%;grid-template-columns:1fr;gap:1.75rem;}
        [data-slipstream-feature]{border-top:1px solid rgba(251,251,250,.22);padding-top:1.1rem;}
        [data-slipstream-feature] h3{margin:0;color:inherit;font-size:1.125rem;font-weight:500;line-height:1.2;letter-spacing:0;}
        [data-slipstream-feature] p{margin:.55rem 0 0;color:rgba(251,251,250,.85);font-size:.9375rem;line-height:1.55;}
        [data-slipstream-no]{display:inline-block;margin-right:.7rem;color:rgba(251,251,250,.85);font:500 .75rem ui-monospace,monospace;letter-spacing:.08em;transform:translateY(-.1em);}
        @container(min-width:768px){[data-slipstream-features]{grid-template-columns:repeat(3,minmax(0,1fr));gap:3.5rem;}}

        /* FraudJobDetector Workstation matching original green theme */
        [data-fjd-panel] {
          width: 100%;
          background: rgba(11, 59, 42, 0.65);
          border: 1px solid rgba(251, 251, 250, 0.22);
          border-radius: 12px;
          padding: 1.5rem;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
        }
        [data-fjd-tab] {
          padding: 6px 14px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 500;
          transition: background .18s, color .18s;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        [data-fjd-tab-active] {
          background: #142b22;
          color: #fff;
          border: 1px solid #10261d;
          box-shadow: 0 1px 2px #10261d1a;
        }
        [data-fjd-tab-inactive] {
          color: rgba(251, 251, 250, 0.75);
          background: transparent;
          border: 1px solid transparent;
        }
        [data-fjd-tab-inactive]:hover {
          color: #fff;
          background: #204434;
        }
        [data-fjd-textarea] {
          width: 100%;
          background: #082d22;
          border: 1px solid rgba(251, 251, 250, 0.22);
          border-radius: 8px;
          color: #fbfbfa;
          padding: 12px;
          font-size: 13px;
          font-family: inherit;
          box-sizing: border-box;
          outline: none;
        }
        [data-fjd-textarea]:focus {
          outline: 2px solid #176247;
          border-color: #176247;
        }
        [data-fjd-btn] {
          min-height: 44px;
          padding: 0 22px;
          background: #142b22;
          border: 1px solid #10261d;
          border-radius: 10px;
          color: #fff;
          font-size: 13px;
          font-weight: 500;
          box-shadow: 0 1px 2px #10261d1a;
          transition: background .18s, box-shadow .18s;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }
        [data-fjd-btn]:hover {
          background: #204434;
          box-shadow: 0 3px 8px #10261d18;
        }
        [data-fjd-btn]:focus-visible {
          outline: 2px solid #176247;
          outline-offset: 4px;
        }
        [data-fjd-upload] {
          border: 2px dashed rgba(251, 251, 250, 0.22);
          border-radius: 10px;
          padding: 2rem;
          text-align: center;
          background: rgba(8, 45, 34, 0.4);
          cursor: pointer;
          transition: border-color .18s;
        }
        [data-fjd-upload]:hover {
          border-color: rgba(251, 251, 250, 0.45);
        }
      `}</style>

      {face ? (
        <GlyphPortal
          word={s.word}
          fontFamily={face}
          fontWeight={700}
          style={{ fontFamily: face }}
          scrollLength={s.scrollLength}
          interactive={s.interactive}
          annotations={s.annotations}
          enterLabel="Verify a Job"
          front={
            <>
              <div data-sublime-header>
                <span data-sublime-logo>FraudJobDetector</span>
                <span data-sublime-category>AI-Powered Job Verification</span>
              </div>
              <p data-sublime-eyebrow>A safer way to discover your next opportunity.</p>
              <p data-sublime-support>Verify the company. Examine the offer. Protect yourself.</p>
              <span data-sublime-scroll>Scroll for a closer look ↓</span>
            </>
          }
        >
          <div data-slipstream-copy>
            <div>
              <h2>Verify Before You Trust.</h2>
              <p
                style={{
                  margin: "0.55rem 0 0",
                  color: "rgba(251,251,250,.85)",
                  fontSize: "1rem",
                  lineHeight: 1.6,
                  maxWidth: "54rem",
                }}
              >
                Analyze suspicious job offers, internship messages, recruitment emails, and company
                identities before sharing your information or accepting an offer.
              </p>
            </div>

            <div data-slipstream-features>
              <div data-slipstream-feature>
                <h3>
                  <span data-slipstream-no>01</span> Job Message Analysis
                </h3>
                <p>Paste a job advertisement, internship message, email, or offer letter for analysis.</p>
              </div>

              <div data-slipstream-feature>
                <h3>
                  <span data-slipstream-no>02</span> Company Identity Verification
                </h3>
                <p>Check available MCA, GST, Udyam, domain, and company-name evidence.</p>
              </div>

              <div data-slipstream-feature>
                <h3>
                  <span data-slipstream-no>03</span> Risk Signals and Safety Guidance
                </h3>
                <p>Review detected warning signs, verification sources, and recommended precautions.</p>
              </div>
            </div>

            {/* Revealed Interactive Verification Section */}
            <div data-fjd-panel>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "1rem",
                  paddingBottom: "1rem",
                  borderBottom: "1px solid rgba(251, 251, 250, 0.15)",
                  marginBottom: "1.25rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    fontWeight: 600,
                    fontSize: "14px",
                    color: "#fbfbfa",
                  }}
                >
                  <Search style={{ width: "16px", height: "16px", opacity: 0.85 }} />
                  <span>Instant Job Offer Scanner</span>
                </div>

                {/* Tab Switcher */}
                <div
                  style={{
                    display: "flex",
                    padding: "3px",
                    background: "#082d22",
                    borderRadius: "10px",
                    border: "1px solid rgba(251, 251, 250, 0.15)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("text");
                      setError(null);
                    }}
                    className={activeTab === "text" ? "data-fjd-tab data-fjd-tab-active" : "data-fjd-tab data-fjd-tab-inactive"}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "7px",
                      fontSize: "12px",
                      fontWeight: 500,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      background: activeTab === "text" ? "#142b22" : "transparent",
                      color: activeTab === "text" ? "#fff" : "rgba(251,251,250,.75)",
                      border: activeTab === "text" ? "1px solid #10261d" : "1px solid transparent",
                    }}
                  >
                    <FileText style={{ width: "14px", height: "14px" }} /> Paste Message
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("offer");
                      setError(null);
                    }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "7px",
                      fontSize: "12px",
                      fontWeight: 500,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      background: activeTab === "offer" ? "#142b22" : "transparent",
                      color: activeTab === "offer" ? "#fff" : "rgba(251,251,250,.75)",
                      border: activeTab === "offer" ? "1px solid #10261d" : "1px solid transparent",
                    }}
                  >
                    <FileUp style={{ width: "14px", height: "14px" }} /> Offer Letter
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("screenshot");
                      setError(null);
                    }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "7px",
                      fontSize: "12px",
                      fontWeight: 500,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      background: activeTab === "screenshot" ? "#142b22" : "transparent",
                      color: activeTab === "screenshot" ? "#fff" : "rgba(251,251,250,.75)",
                      border: activeTab === "screenshot" ? "1px solid #10261d" : "1px solid transparent",
                    }}
                  >
                    <ImageIcon style={{ width: "14px", height: "14px" }} /> Screenshot
                  </button>
                </div>
              </div>

              {error && (
                <div
                  style={{
                    marginBottom: "1.25rem",
                    padding: "10px 14px",
                    borderRadius: "8px",
                    background: "rgba(140, 29, 29, 0.35)",
                    border: "1px solid rgba(239, 68, 68, 0.4)",
                    color: "#fecaca",
                    fontSize: "12px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <AlertCircle style={{ width: "16px", height: "16px", flexShrink: 0 }} />
                  <span>{error}</span>
                </div>
              )}

              {activeTab === "text" ? (
                <form onSubmit={handleAnalyzeJob} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 500,
                        color: "rgba(251,251,250,.85)",
                        marginBottom: "8px",
                      }}
                    >
                      Job Message / Recruitment Text
                    </label>
                    <textarea
                      rows={5}
                      value={jobMessage}
                      onChange={(e) => setJobMessage(e.target.value)}
                      placeholder="Paste suspicious job posting, Telegram hiring offer, WhatsApp recruiter text, or email here..."
                      style={{
                        width: "100%",
                        background: "#082d22",
                        border: "1px solid rgba(251, 251, 250, 0.22)",
                        borderRadius: "8px",
                        color: "#fbfbfa",
                        padding: "12px",
                        fontSize: "13px",
                        fontFamily: "inherit",
                        boxSizing: "border-box",
                        outline: "none",
                      }}
                    />
                  </div>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "1rem",
                      paddingTop: "0.5rem",
                    }}
                  >
                    <div style={{ fontSize: "12px", color: "rgba(251, 251, 250, 0.65)" }}>
                      Statutory registries checked: MCA, GSTIN, Udyam, Domain WHOIS
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      data-gp-enter
                      style={{
                        cursor: "pointer",
                        opacity: loading ? 0.6 : 1,
                        background: "#142b22",
                        border: "1px solid #10261d",
                        borderRadius: "10px",
                        color: "#fff",
                        padding: "0 20px",
                        minHeight: "44px",
                        fontSize: "13px",
                        fontWeight: 500,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      {loading ? (
                        "Extracting Entities…"
                      ) : (
                        <>
                          Analyze Job <ArrowRight style={{ width: "15px", height: "15px" }} />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              ) : (
                <form onSubmit={handleFileUpload} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 500,
                        color: "rgba(251,251,250,.85)",
                        marginBottom: "8px",
                      }}
                    >
                      {activeTab === "offer" ? "Upload Offer Letter Document" : "Upload WhatsApp / Recruitment Screenshot"}
                    </label>
                    <div
                      style={{
                        border: "2px dashed rgba(251, 251, 250, 0.22)",
                        borderRadius: "10px",
                        padding: "2rem",
                        textAlign: "center",
                        background: "rgba(8, 45, 34, 0.4)",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="file"
                        id="portalFileUpload"
                        accept={
                          activeTab === "offer"
                            ? ".pdf,.docx,.jpg,.jpeg,.png"
                            : "image/png,image/jpeg,image/jpg"
                        }
                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                        style={{ display: "none" }}
                      />
                      <label htmlFor="portalFileUpload" style={{ cursor: "pointer", display: "block" }}>
                        <div
                          style={{
                            width: "44px",
                            height: "44px",
                            borderRadius: "10px",
                            background: "#142b22",
                            border: "1px solid rgba(251,251,250,.2)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            margin: "0 auto 10px",
                            color: "#fbfbfa",
                          }}
                        >
                          {activeTab === "offer" ? (
                            <FileUp style={{ width: "20px", height: "20px" }} />
                          ) : (
                            <ImageIcon style={{ width: "20px", height: "20px" }} />
                          )}
                        </div>
                        <div style={{ fontSize: "13px", fontWeight: 500, color: "#fbfbfa", marginBottom: "4px" }}>
                          {file ? file.name : "Click to select a document or screenshot"}
                        </div>
                        <div style={{ fontSize: "11px", color: "rgba(251,251,250,.6)" }}>
                          {activeTab === "offer"
                            ? "Supported formats: PDF, DOCX, JPG, PNG"
                            : "Supported formats: PNG, JPG, JPEG"}
                        </div>
                      </label>
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: "0.5rem" }}>
                    <button
                      type="submit"
                      disabled={loading || !file}
                      style={{
                        cursor: "pointer",
                        opacity: loading || !file ? 0.6 : 1,
                        background: "#142b22",
                        border: "1px solid #10261d",
                        borderRadius: "10px",
                        color: "#fff",
                        padding: "0 20px",
                        minHeight: "44px",
                        fontSize: "13px",
                        fontWeight: 500,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      {loading ? (
                        "Scanning…"
                      ) : (
                        <>
                          Analyze {activeTab === "offer" ? "Offer Letter" : "Screenshot"} <ArrowRight style={{ width: "15px", height: "15px" }} />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </GlyphPortal>
      ) : (
        <div
          role="status"
          style={{
            height: "100%",
            display: "grid",
            placeItems: "center",
            color: "#555",
            fontSize: 12,
          }}
        >
          Loading type…
        </div>
      )}
    </div>
  );
}
