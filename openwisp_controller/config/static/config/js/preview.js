"use strict";
django.jQuery(function ($) {
    var overlay = $('.djnjc-overlay'),
        html = $('html'),
        inner = overlay.find('.inner'),
        preview_url = $('.previewlink').attr('data-url');
    var openPreview = function () {
        var selectors = 'input[type=text], input[type=hidden], select, textarea',
            fields = $(selectors, '#content-main form').not('#id_config_jsoneditor *'),
            $id = $('#id_id'),
            data = {},
            loadingOverlay = $('#loading-overlay');
        loadingOverlay.show();
        // add id to POST data
        // note: may be overridden by fields of OneToOne relation
        if ($id.length) { data.id = $id.val(); }
        // gather data to send in POST
        fields.each(function (i, field) {
            var $field = $(field),
                name = $field.attr('name');
            // skip management fields
            if (!name ||
                name.indexOf('initial-') === 0 ||
                name.indexOf('config-__') === 0 ||
                name.indexOf('_FORMS') != -1) { return; }
            // rename fields of OneToOne relation
            if (name.indexOf('config-0-') === 0) {
                name = name.replace('config-0-', '');
            }
            data[name] = $field.val();
        });
        // show preview
        $.post(preview_url, data, function (htmlContent) {
            inner.html($('#content-main div', htmlContent).html());
            overlay.show();
            html.css('overflow', 'hidden');
            overlay.find('pre').trigger('click');
            // close preview
            overlay.find('.close').click(function (e) {
                e.preventDefault();
                closePreview();
            });
            loadingOverlay.fadeOut(250);
        })
            .fail(function (xhr) {
                // if validation error, show it on page
                if (xhr.status == 400) {
                    alert('There was an issue while generating the preview \n' +
                        'Details: ' + xhr.responseText);
                }
                // 500 internal server error
                // rare case, leaving it untranslated for simplicity
                else {
                    var message = 'Error while generating preview';
                    if (gettext) { message = gettext(message); }
                    alert(message + ':\n\n' + xhr.responseText);
                }
                closePreview();
            });
    };
    var closePreview = function () {
        overlay.hide();
        inner.html('');
        html.attr('style', '');
    };
    $('.previewlink').click(function (e) {
        var configUi = $('#id_config_jsoneditor, #id_config-0-config_jsoneditor'),
            message;
        e.preventDefault();
        // show preview only if there's a configuration
        // (device items may not have one)
        if (configUi.length) {
            openPreview();
        }
        else {
            message = 'No configuration available';
            if (gettext) { message = gettext(message); }
            alert(message);
        }
    });
    $(document).keyup(function (e) {
        // ALT+P
        if (e.altKey && e.which == 80) {
            // unfocus any active input before proceeding
            $(document.activeElement).trigger('blur');
            // wait for JSON editor to update the
            // corresonding raw value before proceding
            setTimeout(openPreview, 15);
        }
        // ESC
        else if (!e.ctrlKey && e.which == 27) {
            closePreview();
        }
    });
});
