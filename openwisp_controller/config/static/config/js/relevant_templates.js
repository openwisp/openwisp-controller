'use strict';
django.jQuery(function ($) {
    var firstRun = true,
        getTemplateOptionElement = function (index, templateId, templateConfig, isSelected = false, isPrefix = false) {
            var prefix = isPrefix ? '__prefix__-' : '',
                requiredString = templateConfig.required ? ' (required)' : '',
                element = $(`<li class="sortedm2m-item"><label for="id_config-${prefix}templates_${index}"><input type="checkbox" value="${templateId}" id="id_config-${prefix}templates_${index}" class="sortedm2m" data-required=${templateConfig.required}> ${templateConfig.name}${requiredString}</label></li>`),
                inputField = element.children().children('input');

            if (templateConfig.required) {
                inputField.prop('disabled', true);
            }
            if (isSelected || templateConfig.required) {
                inputField.prop('checked', true);
            }
            return element;
        },
        resetTemplateOptions = function () {
            $('ul.sortedm2m-items').empty();
        },
        updateTemplateSelection = function (selectedTemplates) {
            // Marks currently applied templates from database as selected
            // Only executed at page load.
            selectedTemplates.forEach(function (templateId) {
                $(`li.sortedm2m-item input[type="checkbox"][value="${templateId}"]:first`).prop('checked', true);
            });
        },
        updateTemplateHelpText = function () {
            var helpText = 'Choose items and order by drag & drop.';
            if ($('li.sortedm2m-item:first').length === 0) {
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
                backend = $('#id_config-0-backend').val(),
                selectedTemplates;

            // Hide templates if no organization or backend is selected
            if (orgID.length === 0 || backend.length === 0) {
                resetTemplateOptions();
                updateTemplateHelpText();
                return;
            }

            if (firstRun) {
                // selectedTemplates will be undefined on device add page or
                // when the user has changed any of organization or backend field.
                // selectedTemplates will be an empty string if no template is selected
                // ''.split(',') returns [''] hence, this case requires special handling
                selectedTemplates = django._owcInitialValues["config-0-templates"];
                if (selectedTemplates !== undefined) {
                    if (selectedTemplates === '') {
                        selectedTemplates = [];
                    } else {
                        selectedTemplates = selectedTemplates.split(',');
                    }
                }
            }

            var url = window._relevantTemplateUrl.replace('org_id', orgID);
            // Get relevant templates of selected org and backend
            url = url + '?backend=' + backend;
            $.get(url).done(function (data) {
                resetTemplateOptions();
                var enabledTemplates = [],
                    sortedm2mUl = $('ul.sortedm2m-items:first'),
                    sortedm2mPrefixUl = $('ul.sortedm2m-items:last');

                // Adds "li" elements for templates that are already selected
                // in the database. Select these templates and remove their key from "data"
                // This maintains the order of the templates and keep
                // enabled templates on the top
                if (selectedTemplates !== undefined) {
                    selectedTemplates.forEach(function (templateId, index) {
                        var element = getTemplateOptionElement(index, templateId, data[templateId], true, false),
                            prefixElement = getTemplateOptionElement(index, templateId, data[templateId], true, true);
                        sortedm2mUl.append(element);
                        sortedm2mPrefixUl.append(prefixElement);
                        delete data[templateId];
                    });
                }

                // Adds "li" elements for templates that are not selected
                // in the database.
                var counter = selectedTemplates !== undefined ? selectedTemplates.length : 0;
                Object.keys(data).forEach(function (templateId, index) {
                    index = index + counter;
                    var isSelected = (data[templateId].default && (selectedTemplates === undefined)) && (!data[templateId].required),
                        element = getTemplateOptionElement(index, templateId, data[templateId], isSelected),
                        prefixElement = getTemplateOptionElement(index, templateId, data[templateId], isSelected, true);
                    // Default templates should only be enabled for new
                    // device or when user has changed any of organization
                    // or backend field
                    if (isSelected === true) {
                        enabledTemplates.push(templateId);
                    }
                    sortedm2mUl.append(element);
                    sortedm2mPrefixUl.append(prefixElement);
                });
                if (firstRun === true && selectedTemplates !== undefined) {
                    updateTemplateSelection(selectedTemplates);
                }
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
            firstRun = false;
            $('#content-main form').submit(function () {
                $('ul.sortedm2m-items:first input[type="checkbox"][data-required="true"]').prop('checked', false);
            });
        };
    window.bindDefaultTemplateLoading = bindDefaultTemplateLoading;
});
