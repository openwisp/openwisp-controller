'use strict';
django.jQuery(function ($) {
    var type_select = $('#id_type'),
        vpn_specific = $('.field-vpn, .field-auto_cert'),
        gettext = window.gettext || function (v) { return v; },
        toggle_vpn_specific = function (changed) {
            if (type_select.val() == 'vpn') {
                vpn_specific.show();
                if (changed === true && $('.autovpn').length < 1 && $('#id_config').val() === '{}') {
                    var p1 = gettext('Click on Save to automatically generate the ' +
                        'VPN client configuration (will be based on ' +
                        'the configuration of the server).'),
                        p2 = gettext('You can then tweak the VPN client ' +
                            'configuration in the next step.');
                    $('.jsoneditor-wrapper').hide()
                        .after('<div class="form-row autovpn"></div>');
                    $('.autovpn').html('<p><strong>' + p1 + '</strong></p>' +
                        '<p><strong>' + p2 + '</strong></p>');
                }
            }
            else {
                vpn_specific.hide();
                if ($('.autovpn').length > 0) {
                    $('.jsoneditor-wrapper').show();
                    $('.autovpn').hide();
                }
            }
        };
    type_select.on('change', function () {
        toggle_vpn_specific(true);
    });
    toggle_vpn_specific();
});
