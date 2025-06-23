"use strict";
django.jQuery(function ($) {
  const $addForm = $(".add-form");
  const $deviceForm = $("#device_form");

  if ($addForm.length || !$deviceForm.length) {
    return;
  }
  const deviceId = $('input[id="id_uuid"]').val();
  const $parentDiv = $("#overview-group .field-last_ip div:last");
  const whoIsInfoUrl = new URL(
    "/admin/config/device/get-who-is-info/",
    window.location.origin,
  );
  whoIsInfoUrl.searchParams.set("device_id", deviceId);

  $.get(whoIsInfoUrl).done(function (data) {
    $parentDiv.after(
      `<div>These details are based on last public IP: ${data.ip_address}</div>
        <table id="who_is_table">
          <tr>
            <th>ISP <span title="This is the Organization associated with registered ASN" id="isp_info">i</span></th>
            <th>Country</th>
          </tr>
          <tr>
            <td>${data.isp}</td>
            <td>${data.address.country}</td>
          </tr>
        </table>
        <details id="who_is_details">
          <summary>
            <span class="who_is_globe"></span>
            <div>
              <span>Additional Details</span><span class="mg-arrow"></span>
            </div>
          </summary>
          <div>
            <p>ASN : ${data.asn}</p>
            <p>Timezone : ${data.timezone}</p>
            <p>Address : ${data.formatted_address}</p>
            <p>CIDR : ${data.cidr}</p>
          </div>
        </details>`,
    );
  });
});
