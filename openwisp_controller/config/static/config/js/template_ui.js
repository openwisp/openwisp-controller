// Created to show or hide the ca and blueprint_cert fields
// based on the selected template type.
django.jQuery(function ($) {
  var typeField = $("#id_type"),
    caField = $(".field-ca"),
    blueprintField = $(".field-blueprint_cert");

  // Only the Template admin form has the type selector; bail out elsewhere
  // (e.g. VpnAdmin) to avoid hiding its unrelated `.field-ca` row.
  if (!typeField.length) {
    return;
  }
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
