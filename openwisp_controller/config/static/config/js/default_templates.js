'use strict';
django.jQuery(function ($) {
    var firstRun = true,
        addChangeEventToBackend = function (urls) {
            $('#id_config-0-backend').change(function () {
                setTimeout(function () {
                    // ensures getDefaultTemplates execute only after other
                    // onChange event handlers attached this field has been
                    // executed.
                    getRelevantTemplates();
                    getDefaultTemplates(urls);
                });
            });
        },
        unCheckInputs = function () {
            $('input.sortedm2m').prop('checked', false);
            $('input[name="config-0-templates"]').attr('value', "");
            if (window.hasOwnProperty('updateContext')) {
                window.updateContext();
            }
        },
        getDefaultTemplates = function (urls) {
            var orgID = $('#id_organization').val(),
                backend = $('#id_config-0-backend').val();
            // proceed only if an organization and a backend have been selected
            if (orgID.length === 0 || backend.length === 0) {
                unCheckInputs();
                return;
            }
            var url = urls[orgID],
                isNew = $('#id_config-0-id').length === 0;
            // if device is not new, do not execute on page load
            if (!isNew && firstRun) {
                return;
            }
            // if no url
            if (!url) {
                unCheckInputs();
                return;
            }
            // get default templates of selected org and backend
            url = url + '?backend=' + backend;
            $.get(url).done(function (data) {
                unCheckInputs();
                $.each(data.default_templates, function (i, uuid) {
                    $('input.sortedm2m[value=' + uuid + ']').trigger('click');
                });
            });
        },
        getRelevantTemplates = function () {
            var orgID = $('#id_organization').val(),
                backend = $('#id_config-0-backend').val();
            if (!orgID || !backend) {
                return;
            }
            // proceed only if an organization and a backend have been selected
            if (orgID.length === 0 || backend.length === 0) {
                return;
            }
            var url = '/admin/config/device/config/get-relevant-templates/';
            // get relevant templates of selected org and backend
            url = url + orgID + '/' + '?backend=' + backend;
            $.get(url).done(function (data) {
                var relevantTemplates = {};
                $.each(data.templates, function (i, uuid) {
                    relevantTemplates[uuid] = uuid;
                });
                $('input.sortedm2m').each(function () {
                    if (($(this).val() in relevantTemplates) === false) {
                        // hide templates which are not relevant
                        // also removed disabled attribute and uncheck it
                        $(this).prop("disabled", false);
                        $(this).prop("checked", false);
                        $(this).parent().parent().hide();
                    } else {
                        // show templates which are relevant
                        $(this).parent().parent().show();
                    }
                });
                // change help text if no relevant template
                var msg = "Choose items and order by drag & drop.";
                if (Object.keys(relevantTemplates).length === 0) {
                    msg = "No Template available";
                }
                if (gettext) {
                    msg = gettext(msg);
                }
                $('.sortedm2m-container > .help').text(msg);
            });
        },
        bindDefaultTemplateLoading = function (urls) {
            var backendField = $('#id_config-0-backend');
            $('#id_organization').change(function () {
                if ($('#id_config-0-backend').length > 0) {
                    getRelevantTemplates();
                    getDefaultTemplates(urls);
                }
            });
            if (backendField.length > 0) {
                addChangeEventToBackend(urls);
            } else {
                $('#config-group > fieldset.module').ready(function () {
                    $('div.add-row > a').click(function () {
                        addChangeEventToBackend(urls);
                        getRelevantTemplates();
                        getDefaultTemplates(urls);
                    });
                });
            }
            firstRun = false;
        };
    window.bindDefaultTemplateLoading = bindDefaultTemplateLoading;
    $(document).ready(function () {
        getRelevantTemplates();
    });
});
