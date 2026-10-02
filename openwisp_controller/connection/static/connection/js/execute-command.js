"use strict";

const EXCLUDED_STORAGE_PREFIX = "ow-batch-command-excluded:";
const WIZARD_SELECTS = "#id_type, #id_organization, #id_group, #id_location";
const COMMAND_EDITOR_ID = "id_input_jsoneditor";

django.jQuery(function ($) {
  initExecuteCommandForm($);
  initDeviceSelection($);
});

function initExecuteCommandForm($) {
  const $typeSelect = $("#id_type");
  if (!$typeSelect.length) {
    return;
  }
  const $form = $typeSelect.closest("form");

  clearAbandonedExclusions();

  $(WIZARD_SELECTS).select2({
    theme: "default",
    placeholder: gettext("Select an option"),
    allowClear: true,
    width: "resolve",
  });

  initOrganizationScope($);
  initCommandInput($, $typeSelect);

  // admin pages are served no-store, so a back navigation restores the field
  // values after select2 has already rendered its labels
  $(window).on("pageshow", function () {
    $(WIZARD_SELECTS).each(function () {
      const $field = $(this);
      if ($field.data("select2")) {
        $field.trigger("change.select2");
      }
    });
  });

  $form.on("submit", function (event) {
    clearFieldErrors($);
    const type = $typeSelect.val();
    let hasError = false;
    if (!type) {
      showFieldError(
        $typeSelect.closest(".form-row"),
        gettext("This field is required."),
      );
      hasError = true;
    }
    if (!$.trim($("#id_label").val() || "")) {
      showFieldError(
        $("#id_label").closest(".form-row"),
        gettext("This field is required."),
      );
      hasError = true;
    }
    if (showCommandErrors($)) {
      hasError = true;
    }
    if (hasError) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  });
}

// mirrors checkInputIsValid() in commands.js: the editor renders its errors as
// soon as it is built, so they are kept hidden until the form is submitted
function showCommandErrors($) {
  const editor = (django._jsonEditors || {})[COMMAND_EDITOR_ID];
  if (!editor) {
    return false;
  }
  const errors = editor.validate();
  // a field is redisplayed only when it was edited or when "show_errors"
  // changed since the last call, "always" skips both checks
  editor.options.show_errors = "always";
  editor.root.showValidationErrors(errors);
  $("#" + COMMAND_EDITOR_ID).addClass("command-errors");
  return errors.length > 0;
}

// with no type the editor is handed the whole schema map and renders it as a
// generic root object
function initCommandInput($, $typeSelect) {
  function toggle() {
    $(document.body).toggleClass("no-command-type", !$typeSelect.val());
    // the container is reused, its errors belong to the previous type
    $("#" + COMMAND_EDITOR_ID).removeClass("command-errors");
  }

  $typeSelect.on("change", toggle);
  toggle();
}

function initOrganizationScope($) {
  const $organization = $("#id_organization");
  const fields = ["#id_group", "#id_location"].filter(function (selector) {
    return $(selector).length;
  });
  if (!fields.length) {
    return;
  }
  fields.forEach(function (selector) {
    $(selector).data("allOptions", $(selector).find("option").clone());
  });

  function applyScope() {
    const organizationId = $organization.val() || "";
    fields.forEach(function (selector) {
      const $field = $(selector);
      const current = $field.val();
      const $options = $field.data("allOptions").filter(function () {
        const value = $(this).attr("value");
        return (
          !value ||
          !organizationId ||
          $(this).attr("data-organization-id") === organizationId
        );
      });
      $field.empty().append($options.clone());
      $field.val($options.filter('[value="' + current + '"]').length ? current : "");
      $field.trigger("change.select2");
    });
  }

  $organization.on("change", applyScope);
  applyScope();
}

function initDeviceSelection($) {
  const $form = $("#execute-form");
  if (!$form.length) {
    return;
  }
  // sessionStorage outlives the wizard, so the key is namespaced by its token
  const storageKey = EXCLUDED_STORAGE_PREFIX + ($form.data("wizard-token") || "");
  const $table = $("#result_list");
  const $excludedField = $("#id_excluded");
  const $count = $("#selected-count");
  const $countLabel = $("#selected-count-label");
  const $button = $("#execute-button");
  const totalDevices = parseInt($form.data("total-devices"), 10) || 0;
  const excluded = getStoredExclusions($, storageKey);

  function updateSelectionSummary() {
    const pks = Object.keys(excluded);
    const selected = Math.max(totalDevices - pks.length, 0);
    $excludedField.val(pks.join(","));
    setStoredExclusions(storageKey, pks);
    $count.text(selected);
    $countLabel.text(ngettext("device", "devices", selected));
    $button.text(
      interpolate(ngettext("Execute on %s device", "Execute on %s devices", selected), [
        selected,
      ]),
    );
    $button.prop("disabled", selected === 0);
    updateSelectAllCheckbox();
  }

  function updateSelectAllCheckbox() {
    const $checkboxes = $table.find(".device-checkbox");
    $("#select-all-devices").prop(
      "checked",
      $checkboxes.length > 0 &&
        $checkboxes.filter(":checked").length === $checkboxes.length,
    );
  }

  $table.on("change", ".device-checkbox", function () {
    const pk = $(this).val();
    if (this.checked) {
      delete excluded[pk];
    } else {
      excluded[pk] = true;
    }
    updateSelectionSummary();
  });

  // devices the user cannot see are never toggled implicitly
  $table.on("change", "#select-all-devices", function () {
    const checked = this.checked;
    $table.find(".device-checkbox").each(function () {
      const $checkbox = $(this);
      if ($checkbox.prop("checked") !== checked) {
        $checkbox.prop("checked", checked).trigger("change");
      }
    });
  });

  $form.on("submit", function () {
    // guards against a double click creating two mass commands
    $button.prop("disabled", true);
  });

  renderSelectAllCheckbox($, $table);
  restoreDeviceCheckboxes($, $table, excluded);
  updateSelectionSummary();
}

function renderSelectAllCheckbox($, $table) {
  const $header = $table.find("thead th").first();
  if (!$header.length || $header.find("#select-all-devices").length) {
    return;
  }
  $header.append(
    $("<input>").attr({
      type: "checkbox",
      id: "select-all-devices",
      title: gettext("Select all devices on this page"),
    }),
  );
}

function restoreDeviceCheckboxes($, $table, excluded) {
  $table.find(".device-checkbox").each(function () {
    const $checkbox = $(this);
    $checkbox.prop("checked", !excluded[$checkbox.val()]);
  });
}

// paging the device table is an ordinary page load, which would forget them
function getStoredExclusions($, storageKey) {
  const stored = {};
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    $.each(raw ? JSON.parse(raw) : [], function (index, pk) {
      stored[pk] = true;
    });
  } catch (error) {
    // private browsing modes can make sessionStorage unavailable
  }
  return stored;
}

function setStoredExclusions(storageKey, pks) {
  try {
    window.sessionStorage.setItem(storageKey, JSON.stringify(pks));
  } catch (error) {
    // see getStoredExclusions()
  }
}

function clearAbandonedExclusions() {
  try {
    const storage = window.sessionStorage;
    for (let i = storage.length - 1; i >= 0; i--) {
      const key = storage.key(i);
      if (key && key.indexOf(EXCLUDED_STORAGE_PREFIX) === 0) {
        storage.removeItem(key);
      }
    }
  } catch (error) {
    // see getStoredExclusions()
  }
}

function clearFieldErrors($) {
  $(".form-row.errors").removeClass("errors");
  $(".form-row .errorlist").not(".jsoneditor .errorlist").remove();
}

function showFieldError($row, message) {
  $row.addClass("errors");
  $row.prepend('<ul class="errorlist"><li>' + message + "</li></ul>");
}
