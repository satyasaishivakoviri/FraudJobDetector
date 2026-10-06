// Background service worker for Fraud Job Detector Extension
chrome.runtime.onInstalled.addListener(() => {
  console.log('[FraudJobDetector] Extension installed and ready.');
});

// Relay messages between popup and active tab if needed
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'ping') {
    sendResponse({ status: 'ok', worker: 'active' });
  }
  return true;
});