"use strict";
django.jQuery(function ($) {
  if ($(".add-form").length) {
    var showOverlay = function () {
      var loading = $("#loading-overlay");
      if (!loading.length) {
        $("body").append(
          '<div id="loading-overlay" class="djnjc-overlay loading"><div class="spinner"></div></div>',
        );
        loading = $("#loading-overlay");
      }
      loading.fadeIn(100, function () {
        loading.css("display", "flex");
        var spinner = loading.find(".spinner");
        spinner.fadeOut(100, function () {
          var message = gettext(
            "Please be patient, we are creating all the necessary " +
              "cyrptographic keys which may take some time",
          );
          spinner.remove();
          loading.append("<p>");
          loading.find("p").hide().text(message).fadeIn(250);
        });
      });
    };

    $("#vpn_form").submit(function () {
      showOverlay();
    });
  }

  var getParentRow = function (el) {
    return el.parents(".form-row").eq(0);
  };

  var toggleRelatedFields = function () {
    // Show IP and Subnet field only for WireGuard backend
    var backendValue =
        $("#id_backend").val() === undefined
          ? ""
          : $("#id_backend").val().toLocaleLowerCase().toLocaleLowerCase(),
      op;
    if (backendValue.includes("wireguard") || backendValue.includes("vxlan")) {
      op = "show";
    } else {
      op = "hide";
    }
    getParentRow($('label[for="id_webhook_endpoint"]'))[op]();
    getParentRow($('label[for="id_auth_token"]'))[op]();

    if (backendValue.includes("openvpn")) {
      op = "show";
    } else {
      op = "hide";
    }
    getParentRow($('label[for="id_ca"]'))[op]();
    getParentRow($('label[for="id_cert"]'))[op]();
    // For Zerotier VPN backend
    if (backendValue.includes("zerotier")) {
      getParentRow($('label[for="id_auth_token"]')).show();
    }
  };

  // clean config when VPN backend is changed
  $("#id_backend").change(function () {
    $("#id_config").val("{}");
    toggleRelatedFields();
  });

  toggleRelatedFields();
});
