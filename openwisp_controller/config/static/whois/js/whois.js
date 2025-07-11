"use strict";
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

  $parentDiv.after(
    `<table class="whois_table">
        <tr>
          <th><span>ISP</span><span title="This is the Organization associated with registered ASN" class="ow-info-icon icon"></span></th>
          <th>Country</th>
        </tr>
        <tr>
          <td>${deviceWHOISDetails.isp}</td>
          <td>${deviceWHOISDetails.address.country}</td>
        </tr>
     </table>
     <details class="whois">
        <summary>
          <span class="whois_globe"></span>
          <div>
            <span>Additional Details</span><span class="mg-arrow"></span>
          </div>
        </summary>
        <div>
          <span class="additional-text">ASN: ${deviceWHOISDetails.asn}</span>
          <span class="additional-text">Timezone: ${deviceWHOISDetails.timezone}</span>
          <span class="additional-text">Address: ${deviceWHOISDetails.formatted_address}</span>
          <span class="additional-text">CIDR: ${deviceWHOISDetails.cidr}</span>
        </div>
     </details>`,
  );
});
