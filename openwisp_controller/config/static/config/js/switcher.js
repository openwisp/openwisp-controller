"use strict";
django.jQuery(function ($) {
  var type_select = $("#id_type"),
    vpn_specific = $(".field-vpn"),
    cert_specific = $(".field-ca, .field-blueprint_cert"),
    auto_cert_field = $(".field-auto_cert"),
    auto_cert_label = $("label[for='id_auto_cert']"),
    gettext =
      window.gettext ||
      function (v) {
        return v;
      },
    toggle_specific_fields = function (changed) {
      var val = type_select.val();
      if (val === "vpn") {
        vpn_specific.show();
        if (
          changed === true &&
          $(".autovpn").length < 1 &&
          $("#id_config").val() === "{}"
        ) {
          var p1 = gettext(
              "Click on Save to automatically generate the " +
                "VPN client configuration (will be based on " +
                "the configuration of the server).",
            ),
            p2 = gettext(
              "You can then tweak the VPN client " + "configuration in the next step.",
            );
          $(".jsoneditor-wrapper").hide().after('<div class="form-row autovpn"></div>');
          $(".autovpn").html(
            "<p><strong>" + p1 + "</strong></p>" + "<p><strong>" + p2 + "</strong></p>",
          );
        }
      } else {
        vpn_specific.hide();
        if ($(".autovpn").length > 0) {
          $(".jsoneditor-wrapper").show();
          $(".autovpn").hide();
        }
      }
      if (val === "cert") {
        cert_specific.show();
      } else {
        cert_specific.hide();
      }
      if (val === "vpn" || val === "cert") {
        auto_cert_field.show();
      } else {
        auto_cert_field.hide();
      }
      if (val === "vpn" || val === "cert") {
        auto_cert_field.show();

        if (val === "vpn") {
          auto_cert_label.text(gettext("Automatic tunnel provisioning"));
        } else if (val === "cert") {
          auto_cert_label.text(gettext("Automatic certificate provisioning"));
        }
      } else {
        auto_cert_field.hide();
      }
    };
  type_select.on("change", function () {
    toggle_specific_fields(true);
  });
  toggle_specific_fields();
});
