"use strict";

if (typeof gettext === "undefined") {
  var gettext = function (word) {
    return word;
  };
}

django.jQuery(function ($) {
  if ($("#subnetdivisionrule_set-group").length === 0) {
    return;
  }
  // Do not allow decreasing number_of_ips
  $('input[name$="-number_of_ips"]:visible').each(function (index, el) {
    if ($(el).val() !== "" && $(el).attr("min") === "0") {
      $(el).attr("min", $(el).val());
    }
  });

  // Disable size and number_of_subnets fields for existing rules
  $(".inline-related.dynamic-subnetdivisionrule_set:visible").each(
    function (index, el) {
      // Delete link appears only on unsaved rules.
      if ($(el).find(".inline-deletelink").length === 0) {
        $(el).find('input[name$="-size"]').prop("readonly", true);
        $(el).find('input[name$="-size"]').addClass("readonly");
        $(el).find('input[name$="-number_of_subnets"]').prop("readonly", true);
        $(el).find('input[name$="-number_of_subnets"]').addClass("readonly");
      }
    },
  );

  // If subnet is not shared, hide organization field from Subnet Division Rule
  function hideOrganizationFieldForNonSharedSubnet() {
    var subnetOrg = $("#id_organization"),
      orgId = subnetOrg.val();
    $('#subnetdivisionrule_set-group select[name$="-organization"]').each(
      function (index, element) {
        element = $(element);
        var row = element.closest(".form-row");
        if (!orgId || (element.val() && element.val() !== orgId)) {
          row.show();
          return;
        }
        if (element.val() !== orgId) {
          // The autocomplete widget loads its options on demand,
          // hence the option of the subnet organization may be missing
          if (element.find('option[value="' + orgId + '"]').length === 0) {
            element.append(new Option(subnetOrg.find("option:selected").text(), orgId));
          }
          element.val(orgId).trigger("change");
        }
        row.hide();
      },
    );
  }
  hideOrganizationFieldForNonSharedSubnet();
  document.addEventListener("formset:added", function (event) {
    if (event.detail.formsetName === "subnetdivisionrule_set") {
      hideOrganizationFieldForNonSharedSubnet();
    }
  });
  $("#id_organization").change(hideOrganizationFieldForNonSharedSubnet);
});
