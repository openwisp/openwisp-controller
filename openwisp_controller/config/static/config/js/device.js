"use strict";
django.jQuery(function ($) {
  if ($(".add-form").length || !$("#device_form").length) {
    return;
  }

  // replaces the management ip field with text with the option to edit it
  var ip_input = $(".field-management_ip > div > input");
  var initial_ip = ip_input.val();
  var management_ip_alt = gettext("Edit");
  ip_input.after(function () {
    ip_input.hide();
    return (
      '<span class="readonly" id="management_ip_text">' +
      (initial_ip === "" ? "-" : initial_ip) +
      "</span>"
    );
  });
  $("#management_ip_text").after(function () {
    return (
      '<a id="edit_management_ip"><img value="edit" src="/static/admin/img/icon-changelink.svg" alt="' +
      management_ip_alt +
      '" title="' +
      management_ip_alt +
      '"></a>'
    );
  });
  $("#edit_management_ip").click(function () {
    var ip_text = $("#management_ip_text");
    var img_element = $("#edit_management_ip > img");
    if (img_element.attr("value") === "edit") {
      ip_input.show();
      ip_text.hide();
      management_ip_alt = gettext("Cancel");
      img_element.attr("src", "/static/admin/img/icon-deletelink.svg");
      img_element.attr("value", "cancel");
      img_element.attr("alt", management_ip_alt);
      img_element.attr("title", management_ip_alt);
    } else {
      ip_text.show();
      ip_input.hide();
      ip_input.val(initial_ip);
      management_ip_alt = gettext("Edit");
      img_element.attr("src", "/static/admin/img/icon-changelink.svg");
      img_element.attr("value", "edit");
      img_element.attr("alt", management_ip_alt);
      img_element.attr("title", management_ip_alt);
    }
  });
});
