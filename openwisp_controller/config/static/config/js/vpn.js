'use strict';
django.jQuery(function ($) {
    if (!$('.add-form').length) {
        return;
    }

    var showOverlay = function () {
        var loading = $('#loading-overlay');
        if (!loading.length) {
            $('body').append(
                '<div id="loading-overlay" class="djnjc-overlay loading"><div class="spinner"></div></div>'
            );
            loading = $('#loading-overlay');
        }
        loading.fadeIn(100, function () {
            loading.css('display', 'flex');
            var spinner = loading.find('.spinner');
            spinner.fadeOut(100, function () {
                var message = gettext(
                    'Please be patient, we are creating all the necessary ' +
                        'cyrptographic keys which may take some time'
                );
                spinner.remove();
                loading.append('<p>');
                loading.find('p').hide().text(message).fadeIn(250);
            });
        });
    };

    $('#vpn_form').submit(function () {
        showOverlay();
    });
});
