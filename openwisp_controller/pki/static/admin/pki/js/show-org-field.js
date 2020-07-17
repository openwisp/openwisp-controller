'use strict';
django.jQuery(function ($) {
    var showField = function () {
        $('.form-row.field-organization').show();
    };
    $('.field-operation_type select').on('change', function () {
        showField();
    });
});
