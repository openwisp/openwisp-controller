django.jQuery(function ($) {
  "use strict";
  var $type_field = $("#id_type"),
    $floorplan_set = $("#floorplan_set-group"),
    $floorplans_length = $floorplan_set.find(".inline-related.has_original").length,
    type_change_event = function (e) {
      var value = $type_field.val();
      // if value is undefined, check for readonly field
      if (typeof value === "undefined") {
        value = $(".field-type .readonly").text();
        if (value && value.startsWith("Indoor")) {
          $floorplan_set.show();
        } else {
          $floorplan_set.hide();
        }
      }
      if (value === "indoor") {
        $floorplan_set.show();
      } else if (value === "outdoor" && $floorplans_length === 0) {
        $floorplan_set.hide();
      } else if (value === "outdoor" && $floorplans_length > 0) {
        // Confirm deletion on switching indoor to outdoor, if floorplans exist
        var msg = gettext(
          "This location has floorplans associated to it. " +
            "Converting it to outdoor will remove all these floorplans, " +
            "affecting all devices related to this location. " +
            "Do you want to proceed?",
        );
        if (!confirm(msg)) {
          $type_field.val("indoor");
        } else {
          $floorplan_set.hide();
        }
      }
    };
  $type_field.change(type_change_event);
  type_change_event();
});
