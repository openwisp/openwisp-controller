'use strict';
(function ($) {
    $(document).ready( function () {
        if ($(".sortedm2m-items").length < 2) {
            $('.sortedm2m-items').sortable('destroy');
        }
    });
}(django.jQuery));
