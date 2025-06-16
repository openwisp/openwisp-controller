"use strict";
django.jQuery(function ($) {
  if ($(".add-form").length || !$("#device_form").length) {
    return;
  }
  var parentDiv = $("#overview-group .field-last_ip div:last"),
    whoIsInfoUrl =
      window.location.origin + "/admin/config/device/get-who-is-info/";
  whoIsInfoUrl += "?device_id=" + $('input[name="config-0-device"]').val();

  $.get(whoIsInfoUrl).done(function (data) {
    parentDiv.after(
      `<div>These details are based on last public IP: ${data.ip_address}</div>` +
        `<table id="who_is_table"><tr><th>Organization</th><th>Country Code</th></tr><tr><td>${data.organization}</td><td>${data.country_code}</td></tr></table>` +
        `<details id="who_is_details"><summary>Additional Details</summary><div><p>ASN : ${data.asn}</p><p>Timezone : ${data.timezone}</p><p>Address : ${data.address}</p><p>CIDR : ${data.cidr}</p></div></details>`,
    );
  });
});
