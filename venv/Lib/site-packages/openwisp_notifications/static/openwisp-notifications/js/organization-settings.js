"use strict";
(function ($) {
  $(document).ready(function () {
    const webNotificationEnabled = $("#id_notification_settings-0-web");
    const emailNotificationEnabled = $("#id_notification_settings-0-email");

    $(webNotificationEnabled).on("change", function () {
      if (webNotificationEnabled.val() === "False") {
        // If web is set to false, also set email to false
        emailNotificationEnabled.val("False");
      }
    });

    $(emailNotificationEnabled).on("change", function () {
      if (emailNotificationEnabled.val() === "True") {
        // If email is set to true, also set web to true
        webNotificationEnabled.val("True");
      }
    });
  });
})(django.jQuery);
