(function () {
  "use strict";

  var pollInterval = 3000;
  var pollTimer = null;

  function getBatchStatus() {
    var statusEl = document.querySelector(".field-status .readonly");
    if (!statusEl) return null;
    var text = statusEl.textContent.trim().toLowerCase();
    if (text.indexOf("in progress") !== -1) return "in-progress";
    if (text.indexOf("success") !== -1) return "success";
    if (text.indexOf("failed") !== -1) return "failed";
    if (text.indexOf("idle") !== -1) return "idle";
    return null;
  }

  function shouldPoll() {
    var status = getBatchStatus();
    return status === "in-progress" || status === "idle";
  }

  function reloadPage() {
    window.location.reload();
  }

  function startPolling() {
    stopPolling();
    if (!shouldPoll()) return;
    pollTimer = setInterval(reloadPage, pollInterval);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    startPolling();
  });
})();
