"use strict";
django.jQuery(function ($) {
  if (window.copyableFields) {
    window.copyableFields.forEach((copyableField) => {
      var copyableFieldContainer = $(`.field-${copyableField} .readonly`).eq(0);

      copyableFieldContainer.html(`<input readonly id="id_${copyableField}" type="text" 
            class="vTextField readonly" value="${copyableFieldContainer.text()}">`);

      var copyableFieldSelectedId = $(`#id_${copyableField}`);
      copyableFieldSelectedId.click(function () {
        $(this).select();
      });
    });
  }
});
