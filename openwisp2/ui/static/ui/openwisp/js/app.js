(function() {
    'use strict';

    $(document).ready(function ($) {
        // automatically center modal depending on its width
        $('body').delegate('.modal.autocenter', 'show.bs.modal', function (e) {
            var dialog = $(this).find('.modal-dialog'),
            dialog_dimensions = dialog.getHiddenDimensions(),
            coefficient = $(this).attr('data-autocenter-coefficient');

            if (!coefficient) {
                coefficient = 2.1;
            }

            dialog.css({
                width: dialog_dimensions.width,
                right: 0
            });

            // vertically align to center
            var new_height = ($(window).height() - dialog_dimensions.height) / coefficient;
            // ensure new position is greater than zero
            new_height = new_height > 0 ? new_height : 0;
            // set new height
            dialog.css('top', new_height);
        });
    });

    $(window).load(function (e) {
        $('#preloader').fadeOut(255, function () {
            $('body').removeAttr('style');
        });
    });

    $(document).ajaxStop(function () {
        $.toggleLoading('hide');
    });
}());
