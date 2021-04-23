'use strict';
django.jQuery(function ($) {
    var firstRun = true,
        getTemplateOptionElement = function (index, templateId, templateConfig, isSelected = false, isPrefix = false) {
            var prefix = isPrefix ? '__prefix__-' : '',
                requiredString = templateConfig.required ? ' (required)' : '',
                element = $(`<li class="sortedm2m-item"><label for="id_config-${prefix}templates_${index}"><input type="checkbox" value="${templateId}" id="id_config-${prefix}templates_${index}" class="sortedm2m"> ${templateConfig.name}${requiredString}</label></li>`),
                inputField = element.children().children('input');

            if (templateConfig.required) {
                inputField.prop('disabled', true);
            }

            if (isSelected === true) {
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
            selectedTemplates.map(function (templateId) {
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
                selectedTemplates = django._owcInitialValues["config-0-templates"];
                if (selectedTemplates !== undefined) {
                    if (selectedTemplates !== "") {
                        selectedTemplates = selectedTemplates.split(',');
                    } else {
                        selectedTemplates = [];
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

                if (selectedTemplates !== undefined) {
                    selectedTemplates.map(function (templateId, index) {
                        var element = getTemplateOptionElement(index, templateId, data[templateId], true, false),
                            prefixElement = getTemplateOptionElement(index, templateId, data[templateId], true, true);
                        sortedm2mUl.append(element);
                        sortedm2mPrefixUl.append(prefixElement);
                        delete data[templateId];
                    });
                }

                Object.keys(data).map(function (templateId, index) {
                    var isSelected = (data[templateId].default && (selectedTemplates === undefined)) && (!data[templateId].required),
                        element = getTemplateOptionElement(index, templateId, data[templateId], isSelected),
                        prefixElement = getTemplateOptionElement(index, templateId, data[templateId], isSelected, true);
                    if (isSelected == true) {
                        enabledTemplates.push(templateId);
                    }
                    sortedm2mUl.append(element);
                    sortedm2mPrefixUl.append(prefixElement);
                });
                if (selectedTemplates !== undefined && firstRun === true) {
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
        };
    window.bindDefaultTemplateLoading = bindDefaultTemplateLoading;
});
