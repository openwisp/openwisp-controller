"use strict";
django.jQuery(function ($) {
  const $addForm = $(".add-form");
  const $deviceForm = $("#device_form");

  if (
    $addForm.length ||
    !$deviceForm.length ||
    deviceWhoIsDetails === undefined
  ) {
    return;
  }
  const $parentDiv = $("#overview-group .field-last_ip div:last");

  $parentDiv.after(
    `<table id="whois_table">
          <tr>
            <th><span>ISP</span><span title="This is the Organization associated with registered ASN" class="ow-info-icon icon"></span></th>
            <th>Country</th>
          </tr>
          <tr>
            <td>${deviceWhoIsDetails.isp}</td>
            <td>${deviceWhoIsDetails.address.country}</td>
          </tr>
        </table>
        <details id="whois_details">
          <summary>
            <span class="whois_globe"></span>
            <div>
              <span>Additional Details</span><span class="mg-arrow"></span>
            </div>
          </summary>
          <div>
            <span class="additional-text">ASN : ${deviceWhoIsDetails.asn}</span>
            <span class="additional-text">Timezone : ${deviceWhoIsDetails.timezone}</span>
            <span class="additional-text">Address : ${deviceWhoIsDetails.formatted_address}</span>
            <span class="additional-text">CIDR : ${deviceWhoIsDetails.cidr}</span>
          </div>
        </details>`,
  );
});
