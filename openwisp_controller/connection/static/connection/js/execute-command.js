"use strict";

const COMMAND_TYPE_CUSTOM = "custom";
const COMMAND_TYPE_CHANGE_PASSWORD = "change_password";
const EXCLUDED_STORAGE_PREFIX = "ow-batch-command-excluded:";
const WIZARD_SELECTS = "#id_type, #id_organization, #id_group, #id_location";

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
  const $container = $("#command-input-container");
  const fieldName = $("#id_input").length ? $("#id_input").attr("name") : "input";
  const $hiddenInput = getHiddenInput($, $form, fieldName);

  function updateCustomCommandInput() {
    const command = $.trim($container.find("#id_command").val());
    $hiddenInput.val(command ? JSON.stringify({ command: command }) : "");
  }

  function updateChangePasswordInput() {
    const password = $container.find("#id_password").val();
    const confirmPassword = $container.find("#id_confirm_password").val();
    $hiddenInput.val(
      password && confirmPassword
        ? JSON.stringify({
            password: password,
            confirm_password: confirmPassword,
          })
        : "",
    );
  }

  function handleTypeChange() {
    const selected = $typeSelect.val();
    let data = null;
    try {
      data = $hiddenInput.val() ? JSON.parse($hiddenInput.val()) : null;
    } catch (error) {
      data = null;
    }
    $container.empty();
    if (selected === COMMAND_TYPE_CUSTOM) {
      renderCustomCommandField($, $container);
      if (data && data.command) {
        $container.find("#id_command").val(data.command);
      }
      updateCustomCommandInput();
    } else if (selected === COMMAND_TYPE_CHANGE_PASSWORD) {
      renderChangePasswordFields($, $container);
      updateChangePasswordInput();
    } else {
      $hiddenInput.val("");
    }
  }

  // a new mass command starts here, so the devices unselected in an earlier
  // one which was configured but never executed are dropped
  clearAbandonedExclusions();

  $container.on("input", "#id_command", updateCustomCommandInput);
  $container.on(
    "input",
    "#id_password, #id_confirm_password",
    updateChangePasswordInput,
  );
  $typeSelect.on("change", handleTypeChange);
  handleTypeChange();

  $(WIZARD_SELECTS).select2({
    theme: "default",
    placeholder: gettext("Select an option"),
    allowClear: true,
    width: "resolve",
  });

  // admin pages are served with Cache-Control: no-store, so going back
  // restores the form values after select2 has rendered its labels
  $(window).on("pageshow", function () {
    $(WIZARD_SELECTS).each(function () {
      const $field = $(this);
      if ($field.data("select2")) {
        $field.trigger("change.select2");
      }
    });
    if (!$typeSelect.val()) {
      return;
    }
    handleTypeChange();
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
    if (type === COMMAND_TYPE_CUSTOM) {
      const command = $container.find("#id_command").val();
      if (!$.trim(command || "")) {
        showFieldError(
          $container.find(".form-row").first(),
          gettext("This field is required."),
        );
        hasError = true;
      }
    }
    if (type === COMMAND_TYPE_CHANGE_PASSWORD) {
      const $password = $container.find("#id_password");
      const $confirmPassword = $container.find("#id_confirm_password");
      const password = $password.val() || "";
      const confirmPassword = $confirmPassword.val() || "";
      if (!password || !confirmPassword) {
        showFieldError(
          (password ? $confirmPassword : $password).closest(".form-row"),
          gettext("This field is required."),
        );
        hasError = true;
      } else if (password.length < 6 || !$.trim(password)) {
        showFieldError(
          $password.closest(".form-row"),
          gettext("Your password must be at least 6 characters long"),
        );
        hasError = true;
      } else if (password !== confirmPassword) {
        showFieldError(
          $confirmPassword.closest(".form-row"),
          gettext("The two password fields didn't match."),
        );
        hasError = true;
      }
    }
    if (hasError) {
      event.preventDefault();
    }
  });
}

function initDeviceSelection($) {
  const $form = $("#execute-form");
  if (!$form.length) {
    return;
  }
  // sessionStorage lives as long as the browser tab, so the key carries the
  // token of this mass command to stop a new one inheriting its exclusions
  const storageKey = EXCLUDED_STORAGE_PREFIX + ($form.data("wizard-token") || "");
  const $table = $("#result_list");
  const $excludedField = $("#id_excluded");
  const $count = $("#selected-count");
  const $button = $("#execute-button");
  const totalDevices = parseInt($form.data("total-devices"), 10) || 0;
  const excluded = getStoredExclusions($, storageKey);

  function updateSelectionSummary() {
    const pks = Object.keys(excluded);
    const selected = Math.max(totalDevices - pks.length, 0);
    $excludedField.val(pks.join(","));
    setStoredExclusions(storageKey, pks);
    $count.text(selected);
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

  // only the devices listed on the current page are toggled, the ones the
  // user cannot see are never selected or unselected implicitly
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

function getHiddenInput($, $form, fieldName) {
  let $hiddenInput = $form.find('input[name="' + fieldName + '"][type="hidden"]');
  if (!$hiddenInput.length) {
    $hiddenInput = $("<input>").attr({ type: "hidden", name: fieldName });
    $form.append($hiddenInput);
  }
  return $hiddenInput;
}

function renderCustomCommandField($, $container) {
  const $row = $('<div class="form-row"></div>');
  const $flexContainer = $('<div class="flex-container"></div>');
  $flexContainer.append(
    '<label for="id_command" class="required">' + gettext("Command") + "</label>",
  );
  $flexContainer.append('<input type="text" id="id_command" class="vTextField">');
  $row.append($flexContainer);
  $row.append(
    '<div class="help" id="id_command_helptext"><div>' +
      gettext("Enter the shell command to run on all devices") +
      "</div></div>",
  );
  $container.append($row);
}

function renderChangePasswordFields($, $container) {
  const $passwordRow = $('<div class="form-row"></div>');
  const $passwordContainer = $('<div class="flex-container"></div>');
  $passwordContainer.append(
    '<label for="id_password" class="required">' + gettext("New password") + "</label>",
  );
  $passwordContainer.append(
    '<input type="password" id="id_password" name="password" minlength="6" maxlength="30">',
  );
  $passwordRow.append($passwordContainer);
  $passwordRow.append(
    '<div class="help" id="id_password_helptext"><div>' +
      gettext("Password must be at least 6 characters long") +
      "</div></div>",
  );
  $container.append($passwordRow);

  const $confirmRow = $('<div class="form-row"></div>');
  const $confirmContainer = $('<div class="flex-container"></div>');
  $confirmContainer.append(
    '<label for="id_confirm_password" class="required">' +
      gettext("Confirm password") +
      "</label>",
  );
  $confirmContainer.append(
    '<input type="password" id="id_confirm_password" name="confirm_password" minlength="6" maxlength="30">',
  );
  $confirmRow.append($confirmContainer);
  $container.append($confirmRow);
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

// rows are rendered selected by the server, untick the ones excluded earlier
function restoreDeviceCheckboxes($, $table, excluded) {
  $table.find(".device-checkbox").each(function () {
    const $checkbox = $(this);
    $checkbox.prop("checked", !excluded[$checkbox.val()]);
  });
}

// exclusions are kept in sessionStorage because turning a page of the device
// table is an ordinary page load, which would otherwise forget them
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
  $(".form-row .errorlist").remove();
}

function showFieldError($row, message) {
  $row.addClass("errors");
  $row.prepend('<ul class="errorlist"><li>' + message + "</li></ul>");
}
