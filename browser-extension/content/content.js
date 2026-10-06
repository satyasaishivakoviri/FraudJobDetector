// Content script: Extracts public job posting details from web pages
(function() {
  function extractPageJobData() {
    const data = {
      source: "web",
      job_title: "",
      company_name: "",
      company_domain: "",
      job_description: "",
      location: "",
      salary: "",
      employment_type: "",
      recruiter_name: "",
      recruiter_email: "",
      recruiter_phone: "",
      visible_fee_info: "",
      application_url: window.location.href
    };

    const host = window.location.hostname.toLowerCase();

    // 1. Check Schema.org JSON-LD microdata first
    try {
      const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
      for (const script of ldScripts) {
        try {
          const parsed = JSON.parse(script.textContent);
          const items = Array.isArray(parsed) ? parsed : [parsed];
          for (const item of items) {
            if (item && (item["@type"] === "JobPosting" || item.type === "JobPosting")) {
              if (item.title && !data.job_title) data.job_title = item.title;
              if (item.hiringOrganization && !data.company_name) {
                data.company_name = typeof item.hiringOrganization === "string" 
                  ? item.hiringOrganization 
                  : (item.hiringOrganization.name || "");
              }
              if (item.description && !data.job_description) {
                const tempDiv = document.createElement("div");
                tempDiv.innerHTML = item.description;
                data.job_description = tempDiv.textContent.trim().slice(0, 4000);
              }
              if (item.jobLocation && !data.location) {
                if (typeof item.jobLocation === "string") data.location = item.jobLocation;
                else if (item.jobLocation.address) {
                  const addr = item.jobLocation.address;
                  data.location = typeof addr === "string" ? addr : (addr.addressLocality || addr.addressRegion || "");
                }
              }
              if (item.baseSalary && !data.salary) {
                const sal = item.baseSalary;
                data.salary = typeof sal === "string" ? sal : (sal.value ? `${sal.value.value || ''} ${sal.currency || ''}`.trim() : "");
              }
              if (item.employmentType && !data.employment_type) {
                data.employment_type = Array.isArray(item.employmentType) ? item.employmentType.join(", ") : String(item.employmentType);
              }
            }
          }
        } catch (e) {}
      }
    } catch (e) {}

    // 2. Specific selectors for LinkedIn
    if (host.includes("linkedin.com")) {
      data.source = "linkedin";
      
      const compEl = document.querySelector(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, .topcard__org-name-link, .job-card-container__company-name");
      if (compEl && !data.company_name) data.company_name = compEl.textContent.trim();

      const titleEl = document.querySelector(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, .top-card-layout__title, h1.t-24");
      if (titleEl && !data.job_title) data.job_title = titleEl.textContent.trim();

      const descEl = document.querySelector(".jobs-description__content, .jobs-box__html-content, .show-more-less-html__markup");
      if (descEl && !data.job_description) data.job_description = descEl.textContent.trim().slice(0, 4000);

      const locEl = document.querySelector(".job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__bullet, .topcard__flavor--bullet");
      if (locEl && !data.location) data.location = locEl.textContent.trim();

      const recruiterEl = document.querySelector(".message-the-recruiter, .hirer-card__hirer-information");
      if (recruiterEl) {
        data.recruiter_name = recruiterEl.textContent.trim().split("\n")[0].trim();
      }
    } 
    // 3. Specific selectors for Naukri
    else if (host.includes("naukri.com")) {
      data.source = "naukri";
      const compEl = document.querySelector(".jd-header-comp-name, .comp-name, .company-name");
      if (compEl && !data.company_name) data.company_name = compEl.textContent.trim();
      const titleEl = document.querySelector(".jd-header-title, h1.title");
      if (titleEl && !data.job_title) data.job_title = titleEl.textContent.trim();
      const descEl = document.querySelector(".jd-description, .dang-inner-html");
      if (descEl && !data.job_description) data.job_description = descEl.textContent.trim().slice(0, 4000);
      const locEl = document.querySelector(".loc, .location");
      if (locEl && !data.location) data.location = locEl.textContent.trim();
    }
    // 4. Specific selectors for Indeed
    else if (host.includes("indeed.com")) {
      data.source = "indeed";
      const compEl = document.querySelector("[data-company-name='true'], .jobsearch-CompanyInfoContainer a");
      if (compEl && !data.company_name) data.company_name = compEl.textContent.trim();
      const titleEl = document.querySelector(".jobsearch-JobInfoHeader-title, h1");
      if (titleEl && !data.job_title) data.job_title = titleEl.textContent.trim();
      const descEl = document.querySelector("#jobDescriptionText");
      if (descEl && !data.job_description) data.job_description = descEl.textContent.trim().slice(0, 4000);
    }

    // 5. OpenGraph & Semantic HTML Fallbacks
    if (!data.job_title) {
      const ogTitle = document.querySelector("meta[property='og:title']");
      if (ogTitle && ogTitle.content) data.job_title = ogTitle.content.split("|")[0].split("-")[0].trim();
      else if (document.querySelector("h1")) data.job_title = document.querySelector("h1").textContent.trim();
      else data.job_title = document.title.split("|")[0].split("-")[0].trim();
    }

    if (!data.company_name) {
      const ogSite = document.querySelector("meta[property='og:site_name']");
      if (ogSite && ogSite.content && !["linkedin", "indeed", "naukri", "glassdoor"].some(p => ogSite.content.toLowerCase().includes(p))) {
        data.company_name = ogSite.content.trim();
      }
    }

    if (!data.job_description) {
      const ogDesc = document.querySelector("meta[property='og:description'], meta[name='description']");
      if (ogDesc && ogDesc.content) data.job_description = ogDesc.content.trim();
    }

    // 6. Regex scans on page text for suspicious patterns & contact details
    const fullBodyText = document.body ? document.body.innerText : "";

    // Domain inference from link or text if company is domain-like
    if (!data.company_domain) {
      const domainMatch = fullBodyText.match(/\b(?:www\.)?([a-zA-Z0-9-]+\.(?:com|in|org|net|co|io|tech))\b/i);
      if (domainMatch && !["linkedin.com", "naukri.com", "indeed.com", "google.com"].includes(domainMatch[1].toLowerCase())) {
        data.company_domain = domainMatch[1].toLowerCase();
      }
    }

    // Email extraction
    const emailMatch = fullBodyText.match(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/);
    if (emailMatch) {
      data.recruiter_email = emailMatch[0];
    }

    // Phone extraction
    const phoneMatch = fullBodyText.match(/\b(?:\+91[-\s]?)?[6-9]\d{9}\b/);
    if (phoneMatch) {
      data.recruiter_phone = phoneMatch[0];
    }

    // Fee / Payment pattern detection
    const feeMatch = fullBodyText.match(/(?:registration|training|placement|verification|laptop|security|internship)\s+(?:fee|deposit|charge|amount)\s*(?:of|:)?\s*(?:₹|inr|rs\.?)\s*\d+/i);
    if (feeMatch) {
      data.visible_fee_info = feeMatch[0];
    }

    return data;
  }

  // Listen for messages from extension popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extractJobData") {
      const extracted = extractPageJobData();
      sendResponse({ status: "success", data: extracted });
    }
    return true;
  });
})();