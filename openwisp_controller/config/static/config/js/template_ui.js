django.jQuery(function ($) {
  var typeField = $("#id_type"),
    caField = $(".field-ca"),
    blueprintField = $(".field-blueprint_cert");

  function toggleCertFields() {
    if (typeField.val() === "cert") {
      caField.show();
      blueprintField.show();
    } else {
      caField.hide();
      blueprintField.hide();
    }
  }
  typeField.on("change", toggleCertFields);
  toggleCertFields();
});
