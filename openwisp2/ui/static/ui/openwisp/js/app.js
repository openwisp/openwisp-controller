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

        $('#js-logout').click(function(e){
            var url = $(this).attr('href');
            e.preventDefault();
            $.post(url).done(function(){
                window.location = url;
            });
        });

        $('#signin-modal, #signup-modal').on('shown.bs.modal', function(){
            $('input', this).eq(0).focus();
        });

        // password strength
        $('#js-signup-password').pwstrength({
            common: {
                minChar: 1
            },
            ui: {
                container: '#js-password-strength-message',
                viewports: {
                    progress: '.pwstrength_viewport_progress',
                    verdict: '.pwstrength_viewport_verdict'
                },
                verdicts: ['Very weak', 'Weak', 'Normal', 'Medium', 'Strong'],
                scores: [10, 17, 26, 40, 50]
            }
        }).focus(function (e) {
            $('#js-password-strength-message').fadeIn(255);
        });

        // signup link in sign in overlay
        $('#js-signup-link').click(function (e) {
            e.preventDefault();
            $('#signin-modal').modal('hide');
            $('#signup-modal').modal('show');
        });

        // signin link in signup overlay
        $('#js-signin-link').click(function (e) {
            e.preventDefault();
            $('#signup-modal').modal('hide');
            $('#signin-modal').modal('show');
        });
    });

    $(window).load(function (e) {
        $('#preloader').fadeOut(255, function () {
            $('body').removeAttr('style');
        });
    });

    $(document).ajaxStart(function () {
        $.toggleLoading('show');
    }).ajaxStop(function () {
        $.toggleLoading('hide');
    });
}());
