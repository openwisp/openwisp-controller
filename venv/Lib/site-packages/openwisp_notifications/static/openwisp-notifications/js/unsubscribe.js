"use strict";

// Ensure `gettext` is defined
if (typeof gettext === "undefined") {
  var gettext = function (word) {
    return word;
  };
}

function updateSubscription(subscribe) {
  const toggleBtn = document.querySelector("#toggle-btn");
  const subscribedMessage = document.querySelector("#subscribed-message");
  const unsubscribedMessage = document.querySelector("#unsubscribed-message");
  const confirmationMsg = document.querySelector(".confirmation-msg-container");
  const confirmSubscribed = document.querySelector("#confirm-subscribed");
  const confirmUnsubscribed = document.querySelector("#confirm-unsubscribed");
  const errorMessage = document.querySelector("#error-msg-container");
  const managePreferences = document.querySelector("#manage-preferences");
  const footer = document.querySelector(".footer");

  fetch(window.location.href, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ subscribe }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Toggle visibility of messages
        subscribedMessage.classList.toggle("hidden", !subscribe);
        unsubscribedMessage.classList.toggle("hidden", subscribe);

        // Update button text and attribute
        toggleBtn.textContent = subscribe
          ? gettext("Unsubscribe")
          : gettext("Subscribe");
        toggleBtn.dataset.hasSubscribe = subscribe.toString();

        // Show confirmation message
        confirmSubscribed.classList.toggle("hidden", !subscribe);
        confirmUnsubscribed.classList.toggle("hidden", subscribe);
        confirmationMsg.classList.remove("hidden");
      } else {
        showErrorState();
      }
    })
    .catch((error) => {
      console.error("Error updating subscription:", error);
      showErrorState();
    });

  function showErrorState() {
    managePreferences.classList.add("hidden");
    footer.classList.add("hidden");
    errorMessage.classList.remove("hidden");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.querySelector("#toggle-btn");

  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      const isSubscribed = toggleBtn.dataset.hasSubscribe === "true";
      updateSubscription(!isSubscribed);
    });
  }
});
