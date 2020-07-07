django.jQuery(function ($) {
    'use strict';
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
        loading.fadeIn(250, function () {
            loading.css('display', 'flex');
        });
        setTimeout(function () {
            var spinner = loading.find('.spinner');
            spinner.fadeOut(250, function () {
                var message = gettext(
                    'Please be patient, we are creating all the necessary ' +
                        'cyrptographic keys which may take a minute or two ...'
                );
                spinner.remove();
                loading.append('<p>');
                loading.find('p').hide().text(message).fadeIn(250);
            });
        }, 2500);
    };

    $('#vpn_form').submit(function (e) {
        var backendValue = $('#id_backend').val();
        if (backendValue.toLowerCase().indexOf('openvpn') > -1) {
            showOverlay();
        }
    });
});
