django.jQuery(function ($) {
  "use strict";
  // select private_key/certificate field text on click
  $(".field-certificate, .field-private_key")
    .find(".readonly")
    .on("click", function () {
      var range, selection;
      if (window.getSelection) {
        selection = window.getSelection();
        range = document.createRange();
        range.selectNodeContents(this);
        selection.removeAllRanges();
        selection.addRange(range);
      } else if (document.body.createTextRange) {
        range = document.body.createTextRange();
        range.moveToElementText(this);
        range.select();
      }
    });
  var changePopupPage = new RegExp(/\d\/change\/\?/);
  var url = window.location.href;
  var operationType = $(".field-operation_type select");
  // enable switcher only in add forms
  if (
    !operationType.length ||
    $("form .deletelink").length > 0 ||
    changePopupPage.test(url)
  ) {
    $(".field-operation_type").hide();
    return;
  }
  // function for operation_type switcher
  var showFields = function () {
    // define fields for each operation
    var importFields = $(
        ".form-row:not(.field-certificate, .field-operation_type, " +
          ".field-private_key, .field-name, .field-ca, .field-passphrase)",
      ),
      newFields = $(".form-row:not(.field-certificate, .field-private_key)"),
      defaultFields = $(".form-row:not(.field-operation_type)"),
      allFields = $(".form-row"),
      value = operationType.val();
    if (value === "-") {
      allFields.show();
      defaultFields.hide();
    }
    if (value === "new") {
      allFields.hide();
      newFields.show();
    }
    if (value === "import") {
      allFields.show();
      importFields.hide();
    }
  };
  showFields();
  operationType.on("change", function (e) {
    showFields();
  });
});
