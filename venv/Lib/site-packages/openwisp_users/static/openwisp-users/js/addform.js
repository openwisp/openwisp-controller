(function ($) {
  "use strict";
  $(document).ready(function () {
    var superuser = $("#id_is_superuser"),
      staff = $("#id_is_staff"),
      orgs = $("#openwisp_users_organizationuser-group");
    superuser.change(function (e) {
      // when enabling superuser
      if (superuser.is(":checked")) {
        // hide organization details because they're not needed
        orgs.hide();
        // reset all org fields
        orgs.find(".field-is_admin input").prop("checked", false);
        orgs.find(".field-organization select").val("");
        // enable staff too
        if (!staff.is(":checked")) {
          staff.trigger("click");
        }
        // when disabling superuser, show organizations
      } else {
        orgs.show();
      }
    });
    staff.change(function (e) {
      // enable also is_admin in org unless superuser
      if (!superuser.is(":checked")) {
        orgs.find(".field-is_admin input").prop("checked", staff.is(":checked"));
      }
    });
    staff.trigger("change");
    superuser.trigger("change");
  });
})(django.jQuery);
