django.jQuery(function ($) {
  "use strict";

  // Both steps of the mass command workflow load this file. Each section
  // returns early when the element it is anchored to is missing, so only
  // the one belonging to the current page does anything.
  initExecuteCommandForm($);
  initConfirmCommandSelection($);

  ////////////////////////////////////////////////////////////////////////
  // Execute command js
  ////////////////////////////////////////////////////////////////////////

  function initExecuteCommandForm($) {
    var TYPE_CUSTOM = "custom";
    var TYPE_CHANGE_PASSWORD = "change_password";

    var $typeSelect = $("#id_type");
    if (!$typeSelect.length) return;

    var $form = $typeSelect.closest("form");
    var $container = $("#command-input-container");
    var fieldName = $("#id_input").length
      ? $("#id_input").attr("name")
      : "input";
    var $hiddenInput;

    function ensureHiddenInput() {
      $hiddenInput = $form.find(
        'input[name="' + fieldName + '"][type="hidden"]',
      );
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
      var $wrapper = $('<div class="form-row"></div>');
      var $fc = $('<div class="flex-container"></div>');
      $fc.append(
        '<label for="bce-dynamic-command" class="required">' +
          gettext("Command") +
          "</label>",
      );
      $fc.append(
        '<input type="text" id="bce-dynamic-command" name="' +
          fieldName +
          '" class="vTextField">',
      );
      $wrapper.append($fc);
      $wrapper.append(
        '<div class="help" id="bce-dynamic-command_helptext"><div>' +
          gettext("Enter the shell command to run on all devices") +
          "</div></div>",
      );
      $container.append($wrapper);
    }

    function buildChangePasswordField() {
      var $pwRow = $('<div class="form-row"></div>');
      var $pwFc = $('<div class="flex-container"></div>');
      $pwFc.append(
        '<label for="bce-dynamic-password" class="required">' +
          gettext("New password") +
          "</label>",
      );
      $pwFc.append(
        '<input type="password" id="bce-dynamic-password" name="password" minlength="6" maxlength="30">',
      );
      $pwRow.append($pwFc);
      $pwRow.append(
        '<div class="help" id="bce-dynamic-password_helptext"><div>' +
          gettext("Password must be at least 6 characters long") +
          "</div></div>",
      );
      $container.append($pwRow);

      var $cpRow = $('<div class="form-row"></div>');
      var $cpFc = $('<div class="flex-container"></div>');
      $cpFc.append(
        '<label for="bce-dynamic-confirm_password" class="required">' +
          gettext("Confirm password") +
          "</label>",
      );
      $cpFc.append(
        '<input type="password" id="bce-dynamic-confirm_password" name="confirm_password" minlength="6" maxlength="30">',
      );
      $cpRow.append($cpFc);
      $container.append($cpRow);
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

    // Reaching this page starts a new mass command, so drop the device
    // selections of any earlier one the user configured but never executed:
    // they are namespaced per command and would otherwise pile up for as
    // long as the browser tab lives.
    discardAbandonedSelections();

    ensureHiddenInput();
    $container.on("input", "#bce-dynamic-command", syncCustom);
    $container.on(
      "input",
      "#bce-dynamic-password, #bce-dynamic-confirm_password",
      syncPassword,
    );
    $typeSelect.on("change", onTypeChange);
    onTypeChange();

    $("#id_type, #id_organization, #id_group, #id_location").select2({
      theme: "default",
      placeholder: gettext("Select an option"),
      allowClear: true,
      width: "resolve",
    });

    // Admin pages are served with Cache-Control: no-store, so going back to
    // this page re-fetches it and the browser restores the previous form
    // values after select2 has already been initialized, leaving the rendered
    // labels stale. Re-sync the select2 display on every pageshow event.
    $(window).on("pageshow", function () {
      $("#id_type, #id_organization, #id_group, #id_location").each(
        function () {
          var $field = $(this);
          if ($field.data("select2")) $field.trigger("change.select2");
        },
      );
      if ($typeSelect.val()) {
        onTypeChange();
        var data = null;
        try {
          data = $hiddenInput.val() ? JSON.parse($hiddenInput.val()) : null;
        } catch (e) {
          data = null;
        }
        if (data && data.command) {
          $container.find("#bce-dynamic-command").val(data.command);
        }
      }
    });

    function clearAllErrors() {
      $(".form-row.errors").removeClass("errors");
      $(".form-row .errorlist").remove();
    }

    function showFieldError($row, message) {
      $row.addClass("errors");
      $row.prepend('<ul class="errorlist"><li>' + message + "</li></ul>");
    }

    var $reviewBtn = $("#review-command-btn");
    if ($reviewBtn.length) {
      $reviewBtn.on("click", function () {
        clearAllErrors();

        var type = $typeSelect.val();
        var $typeRow = $typeSelect.closest(".form-row");
        var hasError = false;

        if (!type) {
          showFieldError($typeRow, gettext("This field is required."));
          hasError = true;
        }

        var label = $("#id_label").val();
        if (!label || !$.trim(label)) {
          showFieldError(
            $("#id_label").closest(".form-row"),
            gettext("This field is required."),
          );
          hasError = true;
        }

        if (type === TYPE_CUSTOM) {
          var cmd = $container.find("#bce-dynamic-command").val();
          if (!cmd || !$.trim(cmd)) {
            showFieldError(
              $container.find(".form-row").first(),
              gettext("This field is required."),
            );
            hasError = true;
          }
        }

        if (hasError) return;

        $form.submit();
      });
    }
  }

  ////////////////////////////////////////////////////////////////////////
  // Confirm command js
  ////////////////////////////////////////////////////////////////////////

  /*
   * Device selection on the confirm page.
   *
   * Every device matched by the targets chosen on the first step starts
   * selected, unselecting one adds it to the "excluded" list. That list is
   * kept both in a hidden field, submitted when the command is executed, and
   * in sessionStorage, because turning the page of the device table is an
   * ordinary page load: without it, unselecting a device on the first page
   * would be forgotten as soon as the second page is opened.
   */
  var STORAGE_PREFIX = "ow-batch-command-excluded:";

  function discardAbandonedSelections() {
    try {
      var storage = window.sessionStorage;
      for (var i = storage.length - 1; i >= 0; i--) {
        var key = storage.key(i);
        if (key && key.indexOf(STORAGE_PREFIX) === 0) {
          storage.removeItem(key);
        }
      }
    } catch (e) {
      // private browsing modes can make sessionStorage unavailable
    }
  }

  function initConfirmCommandSelection($) {
    var $form = $("#bc-execute-form");
    if (!$form.length) return;

    // Namespaced by the token the server issues for this mass command:
    // sessionStorage lives as long as the browser tab, so a shared key would
    // make a new command inherit the devices unselected by the previous one.
    var STORAGE_KEY = STORAGE_PREFIX + ($form.data("wizard-token") || "");
    var $table = $("#result_list");
    var $excludedField = $("#id_excluded");
    var $count = $("#bc-selected-count");
    var $button = $("#bc-execute-button");
    var totalDevices = parseInt($form.data("total-devices"), 10) || 0;
    var excluded = readStoredExclusions();

    function readStoredExclusions() {
      var stored = {};
      try {
        var raw = window.sessionStorage.getItem(STORAGE_KEY);
        $.each(raw ? JSON.parse(raw) : [], function (index, pk) {
          stored[pk] = true;
        });
      } catch (e) {
        // private browsing modes can make sessionStorage unavailable:
        // the selection is then simply not carried across pages
      }
      return stored;
    }

    function storeExclusions(pks) {
      try {
        window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pks));
      } catch (e) {
        // see readStoredExclusions()
      }
    }

    function clearExclusions() {
      try {
        window.sessionStorage.removeItem(STORAGE_KEY);
      } catch (e) {
        // see readStoredExclusions()
      }
    }

    // rows are rendered selected by the server, restore the ones which were
    // unselected on a previously visited page
    function restoreCheckboxes() {
      $table.find(".bc-select-device").each(function () {
        var $checkbox = $(this);
        $checkbox.prop("checked", !excluded[$checkbox.val()]);
      });
    }

    function refresh() {
      var pks = Object.keys(excluded);
      var selected = Math.max(totalDevices - pks.length, 0);
      $excludedField.val(pks.join(","));
      storeExclusions(pks);
      $count.text(selected);
      $button.text(
        interpolate(
          ngettext("Execute on %s device", "Execute on %s devices", selected),
          [selected],
        ),
      );
      $button.prop("disabled", selected === 0);
      refreshSelectAll();
    }

    function refreshSelectAll() {
      var $checkboxes = $table.find(".bc-select-device");
      var $checked = $checkboxes.filter(":checked");
      $("#bc-select-all").prop(
        "checked",
        $checkboxes.length > 0 && $checked.length === $checkboxes.length,
      );
    }

    // the changelist has no header checkbox of its own once the admin
    // actions are disabled, so add one for the current page
    function addSelectAllCheckbox() {
      var $header = $table.find("thead th").first();
      if (!$header.length || $header.find("#bc-select-all").length) return;
      $header.append(
        $("<input>").attr({
          type: "checkbox",
          id: "bc-select-all",
          title: gettext("Select all devices on this page"),
        }),
      );
    }

    $table.on("change", ".bc-select-device", function () {
      var pk = $(this).val();
      if (this.checked) {
        delete excluded[pk];
      } else {
        excluded[pk] = true;
      }
      refresh();
    });

    // only the devices listed on the current page are affected: devices the
    // user cannot see are never selected or unselected implicitly
    $table.on("change", "#bc-select-all", function () {
      var checked = this.checked;
      $table.find(".bc-select-device").each(function () {
        var $checkbox = $(this);
        if ($checkbox.prop("checked") !== checked) {
          $checkbox.prop("checked", checked).trigger("change");
        }
      });
    });

    $form.on("submit", function () {
      clearExclusions();
      // guards against a double click creating two mass commands, the
      // server discards the second request as well
      $button.prop("disabled", true);
    });

    addSelectAllCheckbox();
    restoreCheckboxes();
    refresh();
  }
});
