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
  // and set it to the organization of the subnet
  function hideOrganizationFieldForNonSharedSubnet(rules) {
    var subnetOrg = $("#id_organization option:selected"),
      orgId = subnetOrg.val();
    rules
      .find('select[name$="-organization"]')
      .not('[name*="__prefix__"]')
      .each(function (index, element) {
        element = $(element);
        // "null" is the value of the "Shared systemwide" option
        if (!orgId || orgId === "null") {
          element.closest(".form-row").show();
          return;
        }
        // Do not change the organization of saved rules: a mismatch
        // must stay visible so that the validation error can be fixed.
        var isNew = !element.closest(".inline-related").hasClass("has_original");
        // The autocomplete widget only contains the selected option
        if (element.val() !== orgId && (isNew || !element.val())) {
          element
            .append(new Option(subnetOrg.text(), orgId, true, true))
            .trigger("change");
        }
        element.closest(".form-row").toggle(element.val() !== orgId);
      });
  }
  var ruleGroup = $("#subnetdivisionrule_set-group");
  hideOrganizationFieldForNonSharedSubnet(ruleGroup);
  $("#id_organization").change(function () {
    hideOrganizationFieldForNonSharedSubnet(ruleGroup);
  });
  document.addEventListener("formset:added", function (event) {
    if (event.detail.formsetName === "subnetdivisionrule_set") {
      hideOrganizationFieldForNonSharedSubnet($(event.target));
    }
  });
});
