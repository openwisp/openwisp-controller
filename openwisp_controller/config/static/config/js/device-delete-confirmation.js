"use strict";

(function ($) {
  $(document).ready(function () {
    $("#warning-ack").click(function (event) {
      event.preventDefault();
      $("#deactivating-warning").slideUp("fast");
      $("#delete-confirm-container").slideDown("fast");
      $('input[name="force_delete"]').val("true");
    });
  });
})(django.jQuery);
