// Popup controller for Fraud Job Detector Browser Extension
const API_URL = "http://127.0.0.1:8000/extension/verify-job";
let currentExtractedData = null;
let lastVerificationResult = null;

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const welcomeView = document.getElementById("welcomeView");
  const reviewView = document.getElementById("reviewView");
  const loadingView = document.getElementById("loadingView");
  const resultView = document.getElementById("resultView");

  const btnInspectPage = document.getElementById("btnInspectPage");
  const btnCancelReview = document.getElementById("btnCancelReview");
  const btnEditAndRecheck = document.getElementById("btnEditAndRecheck");
  const btnOpenFullReport = document.getElementById("btnOpenFullReport");
  const jobForm = document.getElementById("jobForm");

  function switchView(viewElement) {
    [welcomeView, reviewView, loadingView, resultView].forEach(v => v.classList.remove("active"));
    viewElement.classList.add("active");
  }

  // Phase 1: Click "Verify this job" -> Extract data from page and show editable review
  btnInspectPage.addEventListener("click", async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        showReviewForm({ company_name: "" });
        return;
      }

      // Try sending message to content script
      chrome.tabs.sendMessage(tab.id, { action: "extractJobData" }, (response) => {
        if (chrome.runtime.lastError || !response || !response.data) {
          // If content script was not injected, execute script manually
          chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["content/content.js"]
          }, () => {
            chrome.tabs.sendMessage(tab.id, { action: "extractJobData" }, (res2) => {
              const data = (res2 && res2.data) ? res2.data : { company_name: tab.title || "" };
              showReviewForm(data);
            });
          });
        } else {
          showReviewForm(response.data);
        }
      });
    } catch (err) {
      console.warn("Extraction fallback", err);
      showReviewForm({ company_name: "" });
    }
  });

  function showReviewForm(data) {
    currentExtractedData = data || {};
    document.getElementById("inputCompanyName").value = data.company_name || "";
    document.getElementById("inputDomain").value = data.company_domain || "";
    document.getElementById("inputJobTitle").value = data.job_title || "";
    document.getElementById("inputRecruiterEmail").value = data.recruiter_email || "";
    document.getElementById("inputFeeInfo").value = data.visible_fee_info || "";
    document.getElementById("inputDescription").value = data.job_description || "";
    switchView(reviewView);
  }

  btnCancelReview.addEventListener("click", () => {
    switchView(welcomeView);
  });

  btnEditAndRecheck.addEventListener("click", () => {
    switchView(reviewView);
  });

  // Phase 2: User confirms/edits data and clicks "Run Verification"
  jobForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const companyName = document.getElementById("inputCompanyName").value.trim();
    if (!companyName) {
      alert("Company Name is required.");
      return;
    }

    const payload = {
      source: currentExtractedData?.source || "extension",
      company_name: companyName,
      company_domain: document.getElementById("inputDomain").value.trim() || null,
      job_title: document.getElementById("inputJobTitle").value.trim() || null,
      recruiter_email: document.getElementById("inputRecruiterEmail").value.trim() || null,
      visible_fee_info: document.getElementById("inputFeeInfo").value.trim() || null,
      job_description: document.getElementById("inputDescription").value.trim() || null,
      application_url: currentExtractedData?.application_url || null,
      location: currentExtractedData?.location || null,
      salary: currentExtractedData?.salary || null,
      employment_type: currentExtractedData?.employment_type || null,
    };

    switchView(loadingView);

    try {
      const resp = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        throw new Error(`API error ${resp.status}`);
      }

      const result = await resp.json();
      lastVerificationResult = result;
      displayResults(result);
      switchView(resultView);
    } catch (err) {
      alert("Verification request failed. Ensure backend is running on 127.0.0.1:8000.\nError: " + err.message);
      switchView(reviewView);
    }
  });

  function displayResults(data) {
    document.getElementById("resultCompanyName").textContent = data.company_name;

    const level = (data.risk_level || "LOW").toLowerCase();
    const badge = document.getElementById("resultRiskBadge");
    badge.className = `result-risk-badge ${level}`;
    document.getElementById("resultRiskLevel").textContent = `${level.toUpperCase()} RISK`;

    const scoreEl = document.getElementById("resultRiskScore");
    scoreEl.textContent = data.risk_score;

    const msgEl = document.getElementById("resultScoreMessage");
    if (level === "low") {
      msgEl.textContent = "Corroborates with official registries. No critical fraud flags.";
    } else if (level === "medium") {
      msgEl.textContent = "Caution advised. Unverified discrepancies detected.";
    } else {
      msgEl.textContent = "High fraud probability! Strong warning signals identified.";
    }

    // Signals
    const sigList = document.getElementById("resultSignalsList");
    sigList.innerHTML = "";
    const signals = data.warning_signals || [];
    if (signals.length === 0) {
      const li = document.createElement("li");
      li.className = "clean";
      li.textContent = "✓ No warning signals detected in registry check.";
      sigList.appendChild(li);
    } else {
      signals.forEach(sig => {
        const li = document.createElement("li");
        li.textContent = `⚠ ${sig}`;
        sigList.appendChild(li);
      });
    }

    // Safety Recommendations
    const recList = document.getElementById("resultRecsList");
    recList.innerHTML = "";
    const recs = data.safety_recommendations || [];
    recs.slice(0, 3).forEach(rec => {
      const li = document.createElement("li");
      if (typeof rec === "object" && rec !== null) {
        li.innerHTML = `<strong>${rec.title || rec.type}:</strong> ${rec.message}`;
      } else {
        li.textContent = rec;
      }
      recList.appendChild(li);
    });
  }

  // Open Full Report in web app
  btnOpenFullReport.addEventListener("click", () => {
    if (!lastVerificationResult) return;
    const targetUrl = lastVerificationResult.full_report_url
      ? `http://127.0.0.1:8000${lastVerificationResult.full_report_url}`
      : "http://127.0.0.1:8000/results";
    
    chrome.tabs.create({ url: targetUrl });
  });
});