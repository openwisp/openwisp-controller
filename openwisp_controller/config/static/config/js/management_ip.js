"use strict";
django.jQuery(function ($) {
  if ($(".add-form").length || !$("#device_form").length) {
    return;
  }
  var editAltText = gettext("Edit"),
    cancelAltText = gettext("Cancel");

  // replaces the management ip field with text with the option to edit it
  var ipInput = $("#id_management_ip"),
    initialIp = ipInput.val() === "" ? "-" : ipInput.val();
  ipInput.after(function () {
    ipInput.hide();
    return (
      `<span class="readonly" id="management_ip_text">${initialIp}</span>` +
      `<a class="related-widget-wrapper-link change-related" id="edit_management_ip"><img value="edit" src="${window.staticUrl}admin/img/icon-changelink.svg"` +
      ` alt="${editAltText}" title="${editAltText}"></a>`
    );
  });
  $("#edit_management_ip").click(function () {
    var ipReadonly = $("#management_ip_text");
    var imgEl = $("#edit_management_ip > img");
    if (imgEl.attr("value") === "edit") {
      ipInput.show();
      ipReadonly.hide();
      imgEl.attr("src", `${window.staticUrl}admin/img/icon-deletelink.svg`);
      imgEl.attr("value", "cancel");
      imgEl.attr("alt", cancelAltText);
      imgEl.attr("title", cancelAltText);
    } else {
      ipReadonly.show();
      ipInput.hide();
      ipInput.val(initialIp);
      imgEl.attr("src", `${window.staticUrl}admin/img/icon-changelink.svg`);
      imgEl.attr("value", "edit");
      imgEl.attr("alt", editAltText);
      imgEl.attr("title", editAltText);
    }
  });
});
