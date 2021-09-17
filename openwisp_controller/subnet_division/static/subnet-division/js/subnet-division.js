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
});
