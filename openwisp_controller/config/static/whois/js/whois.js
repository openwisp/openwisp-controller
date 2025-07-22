"use strict";

if (typeof gettext === "undefined") {
  var gettext = function (word) {
    return word;
  };
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
          <td>${deviceWHOISDetails.isp}</td>
          <td>${deviceWHOISDetails.address.country}</td>
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
          <span class="additional-text">${gettext("ASN")}: ${deviceWHOISDetails.asn}</span>
          <span class="additional-text">${gettext("Timezone")}: ${deviceWHOISDetails.timezone}</span>
          <span class="additional-text">${gettext("Address")}: ${deviceWHOISDetails.formatted_address}</span>
          <span class="additional-text">${gettext("CIDR")}: ${deviceWHOISDetails.cidr}</span>
        </div>
     </details>`,
  );
});
