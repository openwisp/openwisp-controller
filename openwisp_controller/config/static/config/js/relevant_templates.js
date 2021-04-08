'use strict';
django.jQuery(function ($) {
    var firstRun = true,
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
        resetCheckboxInput = function (element) {
            element.prop('checked', false);
            element.prop('disabled', false);
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
                $('li.sortedm2m-item').hide();
                var elements = $('li.sortedm2m-item input[type="checkbox"]:visible');
                resetCheckboxInput(elements);
                updateTemplateHelpText();
                return;
            }
            var url = window._relevantTemplateUrl.replace('org_id', orgID);
            // Get relevant templates of selected org and backend
            url = url + '?backend=' + backend;
            $.get(url).done(function (data) {
                updateTemplateHelpText();
                var enabledTemplates = [];
                // Loop over all input elements fo  the templates field.
                // If value(templateId) of an element is not in data, then
                //      uncheck, enable and hide the element
                // else.
                //      check, the element and disable if if a required template
                $('input.sortedm2m').each(function () {
                    var templateId = $(this).val();
                    if (data[templateId] === undefined) {
                        resetCheckboxInput($(this));
                        $(this).parent().parent().hide();
                        return;
                    }

                    if (data[templateId].required || data[templateId].default) {
                        enabledTemplates.push(templateId);
                        $(this).prop('checked', true);

                        if (data[templateId].required) {
                            $(this).prop('disabled', true);
                        }
                    }
                    $(this).parent().parent().show();
                });
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
            firstRun = false;
        };
    window.bindDefaultTemplateLoading = bindDefaultTemplateLoading;
});
