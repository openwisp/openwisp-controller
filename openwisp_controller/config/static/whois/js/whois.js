"use strict";

var gettext =
  window.gettext ||
  function (word) {
    return word;
  };
// For XSS prevention
function escapeHtml(text) {
  if (text == null) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
django.jQuery(function ($) {
  const $addForm = $(".add-form");
  const $deviceForm = $("#device_form");

  if (
    $addForm.length ||
    !$deviceForm.length ||
    typeof deviceWHOISDetails === "undefined"
  ) {
    return;
  }
  const $parentDiv = $("#overview-group .field-last_ip div:last");
  const tooltipText = gettext(
    "This is the Organization associated with registered ASN",
  );

  $parentDiv.after(
    `<table class="whois-table">
        <tr>
          <th>
            <div>
              <span>${gettext("ISP")}</span>
              <span title="${tooltipText}" class="ow-info-icon icon"></span>
            </div>
          </th>
          <th>${gettext("Country")}</th>
        </tr>
        <tr>
          <td>${escapeHtml(deviceWHOISDetails.isp)}</td>
          <td>${escapeHtml(deviceWHOISDetails.address.country)}</td>
        </tr>
     </table>
     <details class="whois">
        <summary>
          <span class="whois-globe"></span>
          <div>
            <span>${gettext("Additional Details")}</span><span class="mg-arrow"></span>
          </div>
        </summary>
        <div>
          <span class="additional-text">${gettext("ASN")}: ${escapeHtml(deviceWHOISDetails.asn)}</span>
          <span class="additional-text">${gettext("Timezone")}: ${escapeHtml(deviceWHOISDetails.timezone)}</span>
          <span class="additional-text">${gettext("Address")}: ${escapeHtml(deviceWHOISDetails.formatted_address)}</span>
          <span class="additional-text">${gettext("CIDR")}: ${escapeHtml(deviceWHOISDetails.cidr)}</span>
        </div>
     </details>`,
  );
});
