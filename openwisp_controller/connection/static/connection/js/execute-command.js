django.jQuery(function ($) {
  "use strict";

  var TYPE_CUSTOM = "custom";
  var TYPE_CHANGE_PASSWORD = "change_password";

  var $typeSelect = $("#id_type");
  if (!$typeSelect.length) return;

  var $form = $typeSelect.closest("form");
  var $container = $("#command-input-container");
  var fieldName = $("#id_input").length ? $("#id_input").attr("name") : "input";
  var $hiddenInput;

  function ensureHiddenInput() {
    $hiddenInput = $form.find('input[name="' + fieldName + '"][type="hidden"]');
    if (!$hiddenInput.length) {
      $hiddenInput = $("<input>").attr({ type: "hidden", name: fieldName });
      $form.append($hiddenInput);
    }
  }

  function clearContainer() {
    $container.empty();
  }

  function syncCustom() {
    var val = $container.find("#bce-dynamic-command").val();
    val = $.trim(val);
    $hiddenInput.val(val ? JSON.stringify({ command: val }) : "");
  }

  function syncPassword() {
    var pw = $container.find("#bce-dynamic-password").val();
    var cp = $container.find("#bce-dynamic-confirm_password").val();
    $hiddenInput.val(
      pw && cp ? JSON.stringify({ password: pw, confirm_password: cp }) : "",
    );
  }

  function buildCustomField() {
    var $wrapper = $('<div class="bce-field"></div>');
    $wrapper.append('<label for="bce-dynamic-command">Command</label>');
    $wrapper.append(
      '<input type="text" id="bce-dynamic-command" name="' +
        fieldName +
        '" placeholder="e.g. uptime" class="vTextField">',
    );
    $wrapper.append(
      '<div class="help">Enter the shell command to run on all devices</div>',
    );
    $container.append($wrapper);
  }

  function buildChangePasswordField() {
    var $grid = $('<div class="bce-field-grid"></div>');

    var $pwField = $('<div class="bce-field"></div>');
    $pwField.append('<label for="bce-dynamic-password">New password</label>');
    $pwField.append(
      '<input type="password" id="bce-dynamic-password" name="password" minlength="6" maxlength="30">',
    );
    $grid.append($pwField);

    var $cpField = $('<div class="bce-field"></div>');
    $cpField.append(
      '<label for="bce-dynamic-confirm_password">Confirm password</label>',
    );
    $cpField.append(
      '<input type="password" id="bce-dynamic-confirm_password" name="confirm_password" minlength="6" maxlength="30">',
    );
    $grid.append($cpField);

    $container.append($grid);
    $container.append(
      '<div class="bce-field"><div class="help">Password must be at least 6 characters long</div></div>',
    );
  }

  function onTypeChange() {
    var selected = $typeSelect.val();
    clearContainer();

    if (selected === TYPE_CUSTOM) {
      buildCustomField();
      syncCustom();
    } else if (selected === TYPE_CHANGE_PASSWORD) {
      buildChangePasswordField();
      syncPassword();
    } else {
      $hiddenInput.val("");
    }
  }

  ensureHiddenInput();
  $container.on("input", "#bce-dynamic-command", syncCustom);
  $container.on(
    "input",
    "#bce-dynamic-password, #bce-dynamic-confirm_password",
    syncPassword,
  );
  $typeSelect.on("change", onTypeChange);
  onTypeChange();

  var $reviewBtn = $("#review-command-btn");
  if ($reviewBtn.length) {
    $typeSelect.on("change", function () {
      $reviewBtn.prop("disabled", !$(this).val());
    });
    $reviewBtn.prop("disabled", !$typeSelect.val());

    $reviewBtn.on("click", function () {
      var type = $typeSelect.val();
      if (!type) return;

      var params = new URLSearchParams();
      params.append("type", type);

      var inputVal = $hiddenInput.val();
      if (inputVal) {
        params.append("input", inputVal);
      }

      var label = $("#id_label").val();
      if (label) {
        params.append("label", label);
      }

      var notes = $("#id_notes").val();
      if (notes) {
        params.append("notes", notes);
      }

      var org = $("#id_organization").val();
      if (org) {
        params.append("organization", org);
      }

      var group = $("#id_group").val();
      if (group) {
        params.append("group", group);
      }

      var location = $("#id_location").val();
      if (location) {
        params.append("location", location);
      }

      $("#id_devices option:selected").each(function () {
        params.append("devices", $(this).val());
      });

      var confirmUrl = window.location.href.replace("execute/", "confirm/");
      window.location.href = confirmUrl.split("?")[0] + "?" + params.toString();
    });
  }
});
