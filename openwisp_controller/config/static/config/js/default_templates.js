'use strict';
django.jQuery(function ($) {
    var firstRun = true,
        addChangeEventToBackend = function (urls) {
            $('#id_config-0-backend').change(function () {
                setTimeout(function () {
                    // ensures getDefaultTemplates execute only after other
                    // onChange event handlers attached this field has been
                    // executed.
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
                isNew = $('#id_config-0-id').length == 0;
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
                    $('input.sortedm2m[value=' + uuid + ']').prop('checked', true);
                });
                $('input[name="config-0-templates"]').attr('value', data.default_templates.join(','));
                $('.sortedm2m-items:first').trigger('change');

            });
        },
        bindDefaultTemplateLoading = function (urls) {
            var backendField = $('#id_config-0-backend');
            $('#id_organization').change(function () {
                if ($('#id_config-0-backend').length > 0) {
                    getDefaultTemplates(urls);
                }
            });
            if (backendField.length > 0) {
                addChangeEventToBackend(urls);
            } else {
                $('#config-group > fieldset.module').ready(function () {
                    $('div.add-row > a').click(function () {
                        addChangeEventToBackend(urls);
                        getDefaultTemplates(urls);
                    });
                });
            }
            firstRun = false;
        };
    window.bindDefaultTemplateLoading = bindDefaultTemplateLoading;
});
