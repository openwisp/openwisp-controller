"use strict";

django.jQuery(document).ready(function ($) {
  $("#id_user_consented").change(function () {
    let submitButton = $('#id_metric_collection_consent_form input[type="submit"]');
    if (!submitButton.is(":visible")) {
      $('#id_metric_collection_consent_form input[type="submit"]').show();
    }
  });
});
