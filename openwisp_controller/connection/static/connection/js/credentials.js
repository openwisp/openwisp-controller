'use strict';
django.jQuery(function ($) {
    var selector = $('#id_connector'),
    showFields = function () {
        var fields = $('#credentials_form fieldset > .form-row:not(.field-connector):not(.field-params), .jsoneditor-wrapper'),
            value = selector.val();
        if (!value) {
            fields.hide();
        }
        else {
            fields.show();
        }
    };
    selector.change(function () {
        showFields();
    });

    $('#id_params').on('jsonschema-schemaloaded', function(){
        showFields();
    });
});
