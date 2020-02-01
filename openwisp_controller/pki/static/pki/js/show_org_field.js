django.jQuery(function ($) {
    'use strict';
    var operationType = $('.field-operation_type select');
    // function for operation_type switcher
    var showFields = function () {
        var orgField = $('.form-row.field-organization'),
            value = operationType.val();
        if (value === 'import') {
            orgField.show();
        }
    };
    showFields();
    operationType.on('change', function (e) {
        showFields();
    });
});
