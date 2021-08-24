'use strict';

if (typeof gettext === 'undefined') {
    var gettext = function (word) {
        return word;
    };
}

django.jQuery(function ($) {
    if ($('#subnetdivisionrule_set-group').length === 0) {
        return;
    }
    // Do not allow decreasing number_of_ips
    $('input[name$="-number_of_ips"]:visible').each(function (index, el) {
        if (($(el).val() !== '') && ($(el).attr('min') === "0")) {
            $(el).attr('min', $(el).val());
        }
    });
    // Disable subnet size field
    $('#subnetdivisionrule_set-group input[name$="-size"]:visible').prop('readonly', true);
    $('#subnetdivisionrule_set-group input[name$="-size"]:visible').addClass('readonly');

    // Disable number of subnets field
    $('#subnetdivisionrule_set-group input[name$="-number_of_subnets"]:visible').prop('readonly', true);
    $('#subnetdivisionrule_set-group input[name$="-number_of_subnets"]:visible').addClass('readonly');

    // If subnet is not shared, hide organization field from Subnet Division Rule
    function hideOrganizationFieldForNonSharedSubnet() {
        if ($('#id_organization').val() !== '') {
            $('#subnetdivisionrule_set-group select[name$="-organization"]').each(
                function (index, element) {
                    element = $(element);
                    if ((element.val() === '') || (element.val() === $('#id_organization').val())) {
                        element.val($('#id_organization').val());
                        element.parent().parent().parent().hide();
                    } else {
                        element.parent().parent().parent().show();
                    }
                });
        } else {
            $('#subnetdivisionrule_set-group .form-row.field-organization').show();
        }
    }
    hideOrganizationFieldForNonSharedSubnet();
    $('#subnetdivisionrule_set-group .add-row a').click(hideOrganizationFieldForNonSharedSubnet);
    $('#id_organization').change(hideOrganizationFieldForNonSharedSubnet);

    // Insert change warning
    $('#subnetdivisionrule_set-group .add-row a').click(function () {
        var warningText = gettext('Please keep in mind that once the subnet division rule is created and used, changing "Size" and "Number of Subnets" and decreasing "Number of IPs" will not be possible.') +
            ' ' + gettext('Please read') + ' ' + '<a target="_blank" href="https://github.com/openwisp/openwisp-controller/tree/1.0.x#important-notes">' +
            gettext('documentation') + '</a>' + ' ' + gettext('for more information'),
            html = `<div class="help-text-warning"><img src="/static/admin/img/icon-alert.svg"><p>${warningText}</p><div>`;
        $('.last-related > fieldset:visible:last').before(html);
    });
});
