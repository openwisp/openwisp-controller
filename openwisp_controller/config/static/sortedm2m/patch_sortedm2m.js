'use strict';
(function ($) {
    $(document).ready( function () {
        if ($(".add-form").length || $(".sortedm2m-items").length < 2) {
            $('.sortedm2m-items').sortable('destroy');
        }
    });
}(django.jQuery));
