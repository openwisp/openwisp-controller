"use strict";
django.jQuery(function ($) {
  var firstRun = true,
    backendFieldSelector = "#id_config-0-backend",
    orgFieldSelector = "#id_organization",
    isDeviceGroup = function () {
      return window._deviceGroup;
    },
    templatesFieldName = function () {
      return isDeviceGroup() ? "templates" : "config-0-templates";
    },
    getTemplateOptionElement = function (
      index,
      templateId,
      templateConfig,
      isSelected = false,
      isPrefix = false,
    ) {
      if (templateConfig === undefined) {
        return; // relevant templates do not contain this template
      }
      var prefix = isPrefix ? "__prefix__-" : "",
        requiredString = templateConfig.required ? " (required)" : "",
        backendString =
          isDeviceGroup() && templateConfig.backend
            ? ` (backend: ${templateConfig.backend})`
            : "",
        element = $(
          `<li class="sortedm2m-item"><label for="id_config-${prefix}templates_${index}"><input type="checkbox" value="${templateId}" id="id_config-${prefix}templates_${index}" class="sortedm2m" data-required=${templateConfig.required}> ${templateConfig.name}${requiredString}${backendString}</label></li>`,
        ),
        inputField = element.children().children("input");

      if (templateConfig.required) {
        inputField.prop("disabled", true);
      }
      // mark the template as selected if it is required or if it is enabled for the current device or group
      if (isSelected || templateConfig.required || templateConfig.selected) {
        inputField.prop("checked", true);
      }
      return element;
    },
    resetTemplateOptions = function () {
      $("ul.sortedm2m-items").empty();
    },
    updateTemplateSelection = function (selectedTemplates) {
      // Marks currently applied templates from database as selected
      // Only executed at page load.
      selectedTemplates.forEach(function (templateId) {
        $(
          `li.sortedm2m-item input[type="checkbox"][value="${templateId}"]:first`,
        ).prop("checked", true);
      });
    },
    updateTemplateHelpText = function () {
      var helpText = "Choose items and order by drag & drop.";
      if ($("li.sortedm2m-item:first").length === 0) {
        helpText = "No Template available";
      }
      if (gettext) {
        helpText = gettext(helpText);
      }
      $(".sortedm2m-container > .help").text(helpText);
    },
    addChangeEventHandlerToBackendField = function () {
      $(backendFieldSelector).change(function () {
        setTimeout(function () {
          // ensures getDefaultTemplates execute only after other
          // onChange event handlers attached this field has been
          // executed.
          showRelevantTemplates();
        });
      });
      // Initially request data to populate everything
      showRelevantTemplates();
    },
    updateConfigTemplateField = function (templates) {
      $(`input[name="${templatesFieldName()}"]`).attr(
        "value",
        templates.join(","),
      );
      $("input.sortedm2m:first").trigger("change");
    },
    parseSelectedTemplates = function (selectedTemplates) {
      if (selectedTemplates !== undefined) {
        if (selectedTemplates === "") {
          return [];
        } else {
          return selectedTemplates.split(",");
        }
      }
    },
    getRelevantTemplateUrl = function (orgID, backend) {
      // Returns the URL to fetch relevant templates
      var baseUrl = window._relevantTemplateUrl.replace("org_id", orgID);
      var url = new URL(baseUrl, window.location.origin);

      // Get relevant templates of selected org and backend
      if (backend) {
        url.searchParams.set("backend", backend);
      }
      if (isDeviceGroup() && !$(".add-form").length) {
        // Get the group id from the URL
        // TODO: This is fragile, consider using a more robust way to get the group id.
        var pathParts = window.location.pathname.split("/");
        url.searchParams.set("group_id", pathParts[pathParts.length - 3]);
      } else if ($('input[name="config-0-device"]').length) {
        url.searchParams.set(
          "device_id",
          $('input[name="config-0-device"]').val(),
        );
      }
      return url.toString();
    },
    showRelevantTemplates = function () {
      var orgID = $(orgFieldSelector).val(),
        backend = isDeviceGroup() ? "" : $(backendFieldSelector).val(),
        selectedTemplates;

      // Hide templates if no organization or backend is selected
      if (!orgID || (!isDeviceGroup() && backend.length === 0)) {
        resetTemplateOptions();
        updateTemplateHelpText();
        return;
      }

      if (firstRun) {
        // selectedTemplates will be undefined on device add page or
        // when the user has changed any of organization or backend field.
        // selectedTemplates will be an empty string if no template is selected
        // ''.split(',') returns [''] hence, this case requires special handling
        selectedTemplates = parseSelectedTemplates(
          $('input[name="' + templatesFieldName() + '"]').val(),
        );
      }
      var url = getRelevantTemplateUrl(orgID, backend);
      $.get(url).done(function (data) {
        resetTemplateOptions();
        var enabledTemplates = [],
          sortedm2mUl = $("ul.sortedm2m-items:first"),
          sortedm2mPrefixUl = $("ul.sortedm2m-items:last");

        // Adds "li" elements for templates
        Object.keys(data).forEach(function (templateId, index) {
          var isSelected =
              data[templateId].selected ||
              (data[templateId].default &&
                selectedTemplates === undefined &&
                !data[templateId].required),
            element = getTemplateOptionElement(
              index,
              templateId,
              data[templateId],
              isSelected,
            ),
            prefixElement = getTemplateOptionElement(
              index,
              templateId,
              data[templateId],
              isSelected,
              true,
            );
          // Default templates should only be enabled for new
          // device or when user has changed any of organization
          // or backend field
          if (isSelected === true) {
            enabledTemplates.push(templateId);
          }
          sortedm2mUl.append(element);
          if (!isDeviceGroup()) {
            sortedm2mPrefixUl.append(prefixElement);
          }
        });
        if (firstRun === true && selectedTemplates !== undefined) {
          updateTemplateSelection(selectedTemplates);
        }
        updateTemplateHelpText();
        updateConfigTemplateField(enabledTemplates);
      });
    },
    initTemplateField = function () {
      // sortedm2m generates a hidden input dynamically using rendered input checkbox elements,
      // but because the queryset is set to None in the Django admin, the input is created
      // without a name attribute. This workaround assigns the correct name to the hidden input.
      $('.sortedm2m-container input[type="hidden"][id="undefined"]')
        .first()
        .attr("name", templatesFieldName());
    },
    bindDefaultTemplateLoading = function () {
      initTemplateField();
      var backendField = $(backendFieldSelector);
      $(orgFieldSelector).change(function () {
        // Only fetch templates when backend field is present
        if ($(backendFieldSelector).length > 0 || isDeviceGroup()) {
          showRelevantTemplates();
        }
      });
      // Change view: backendField is rendered on page load
      if (backendField.length > 0) {
        addChangeEventHandlerToBackendField();
      } else if (isDeviceGroup()) {
        // Initially request data to get templates
        initTemplateField();
        showRelevantTemplates();
      } else {
        // Add view: backendField is added when user adds configuration
        $("#config-group > fieldset.module").ready(function () {
          $("div.add-row > a").one("click", function () {
            initTemplateField();
            addChangeEventHandlerToBackendField();
          });
        });
      }
      firstRun = false;
      $("#content-main form").submit(function () {
        $(
          'ul.sortedm2m-items:first input[type="checkbox"][data-required="true"]',
        ).prop("checked", false);
      });
    };
  window.bindDefaultTemplateLoading = bindDefaultTemplateLoading;
});
