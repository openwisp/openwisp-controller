django.jQuery(function ($) {
    'use strict';
    var showField = function () {
        $('.form-row.field-organization').show();
    };
    $('.field-operation_type select').on('change', function (e) {
        showField();
    });
});
