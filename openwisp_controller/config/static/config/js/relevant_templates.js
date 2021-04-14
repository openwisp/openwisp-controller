'use strict';
django.jQuery(function ($) {
    var selectedTemplates = django._owcInitialValues["config-0-templates"].split(','),
        isFirstRun = function () {
            return selectedTemplates.length !== 0;
        },
        getTemplateOptionElement = function (index, templateId, templateName, isPrefix = false) {
            var prefix = isPrefix ? '__prefix__-' : '';
            return $(`<li class="sortedm2m-item"><label for="id_config-${prefix}templates_${index}"><input type="checkbox" value="${templateId}" id="id_config-${prefix}templates_${index}" class="sortedm2m"> ${templateName}</label></li>`);
        },
        resetTemplateOptions = function () {
            $('fieldset ul.sortedm2m-items').empty();
        },
        updateTemplateSelection = function () {
            // Marks currently applied templates from database as selected
            // Only executed at page load.
            selectedTemplates.forEach(function (templateId) {
                $(`li.sortedm2m-item:visible input[type="checkbox"][value="${templateId}"]`).prop('checked', true);
            });
            selectedTemplates.length = 0;
        },
        updateTemplateHelpText = function () {
            var helpText = 'Choose items and order by drag & drop.';
            if ($('li.sortedm2m-item:visible').length === 0) {
                helpText = 'No Template available';
            }
            if (gettext) {
                helpText = gettext(helpText);
            }
            $('.sortedm2m-container > .help').text(helpText);
        },
        addChangeEventHandlerToBackendField = function () {
            $('#id_config-0-backend').change(function () {
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
            $('input[name="config-0-templates"]').attr(
                'value', templates.join(',')
            );
            $('input.sortedm2m:first').trigger('change');
        },
        showRelevantTemplates = function () {
            var orgID = $('#id_organization').val(),
                backend = $('#id_config-0-backend').val();

            // Hide templates if no organization or backend is selected
            if (orgID.length === 0 || backend.length === 0) {
                resetTemplateOptions();
                updateTemplateHelpText();
                return;
            }
            var url = window._relevantTemplateUrl.replace('org_id', orgID);
            // Get relevant templates of selected org and backend
            url = url + '?backend=' + backend;
            $.get(url).done(function (data) {
                resetTemplateOptions();
                var enabledTemplates = [];
                Object.keys(data).map(function (templateId, index) {
                    var element = getTemplateOptionElement(index, templateId, data[templateId].name),
                        prefixElement = getTemplateOptionElement(index, templateId, data[templateId].name, true),
                        inputField = element.children().children('input');

                    if (data[templateId].default && (isFirstRun() !== true)) {
                        inputField.prop('checked', true);
                        enabledTemplates.push(templateId);
                    }

                    if (data[templateId].required) {
                        inputField.prop('disabled', true);
                        inputField.prop('checked', true);
                        enabledTemplates.push(templateId);
                    }

                    $('fieldset ul.sortedm2m-items:visible').append(element);
                    $('fieldset ul.sortedm2m-items:not(:visible)').append(prefixElement);
                });
                updateTemplateSelection();
                updateTemplateHelpText();
                updateConfigTemplateField(enabledTemplates);
            });
        },
        bindDefaultTemplateLoading = function () {
            var backendField = $('#id_config-0-backend');
            $('#id_organization').change(function () {
                // Only fetch templates when backend field is present
                if ($('#id_config-0-backend').length > 0) {
                    showRelevantTemplates();
                }
            });
            // Change view: backendField is rendered on page load
            if (backendField.length > 0) {
                addChangeEventHandlerToBackendField();
            } else {
                // Add view: backendField is added when user adds configuration
                $('#config-group > fieldset.module').ready(function () {
                    $('div.add-row > a').one('click', function () {
                        addChangeEventHandlerToBackendField();
                    });
                });
            }
        };
    window.bindDefaultTemplateLoading = bindDefaultTemplateLoading;
});
