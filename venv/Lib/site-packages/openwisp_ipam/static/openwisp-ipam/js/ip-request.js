/*jslint browser:true */

(function ($) {
  "use strict";

  function getAvailableIp() {
    $.ajax({
      type: "GET",
      url: django.ipamGetNextAvailableIpUrl.replace("0000", $("#id_subnet").val()),
      success: function (res) {
        if (!res) {
          alert("No IP address available");
        }
        $("#id_ip_address").val(res);
      },
    });
  }

  function getURLParameter(name) {
    return decodeURI(
      (new RegExp(name + "=" + "(.+?)(&|$)").exec(location.search) || [null])[1],
    );
  }

  $(document).ready(function () {
    var subnet = $("#id_subnet"),
      ip_address = $(".field-ip_address"),
      description = $(".field-description");
    subnet.change(function (e) {
      if (getURLParameter("_popup") === "1") {
        return;
      }
      if (!subnet.val()) {
        ip_address.hide();
        description.hide();
      } else {
        ip_address.show();
        description.show();
        if (window.location.pathname.indexOf("change") === -1) {
          getAvailableIp();
        }
      }
    });
    subnet.trigger("change");
  });
})(django.jQuery);
