'use strict';
django.jQuery(function ($) {
    if ($('.add-form').length) {
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
    }

    var toggleRelatedFields = function () {
        // Show IP and Subnet field only for WireGuard backend
        var backendValue = $('#id_backend').val() === undefined ? '' : $('#id_backend').val().toLocaleLowerCase().toLocaleLowerCase();
        if (backendValue.includes('wireguard') || backendValue.includes('vxlan')) {
            $('label[for="id_subnet"]').parent().parent().show();
            $('label[for="id_ip"]').parent().parent().show();
            $('label[for="id_webhook_endpoint"]').parent().parent().show();
            $('label[for="id_auth_token"]').parent().parent().show();
        } else {
            $('label[for="id_subnet"]').parent().parent().hide();
            $('label[for="id_ip"]').parent().parent().hide();
            $('label[for="id_webhook_endpoint"]').parent().parent().hide();
            $('label[for="id_auth_token"]').parent().parent().hide();
            // Reset IP and Subnet fields
            $('#id_subnet').val(null);
            $('#id_ip').val(null);
        }

        if (backendValue.includes('openvpn')) {
            $('label[for="id_ca"]').parent().parent().show();
            $('label[for="id_cert"]').parent().parent().show();
        } else {
            $('label[for="id_ca"]').parent().parent().hide();
            $('label[for="id_cert"]').parent().parent().hide();
        }
    };

    // clean config when VPN backend is changed
    $('#id_backend').change(function () {
        $('#id_config').val('{}');
        toggleRelatedFields();
    });

    toggleRelatedFields();
});
