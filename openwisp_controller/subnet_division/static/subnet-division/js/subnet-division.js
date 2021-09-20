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

    // Disable size and number_of_subnets fields for existing rules
    $('.inline-related.dynamic-subnetdivisionrule_set:visible').each(function (index, el) {
        // Delete link appears only on unsaved rules.
        if ($(el).find('.inline-deletelink').length === 0) {
            $(el).find('input[name$="-size"]').prop('readonly', true);
            $(el).find('input[name$="-size"]').addClass('readonly');
            $(el).find('input[name$="-number_of_subnets"]').prop('readonly', true);
            $(el).find('input[name$="-number_of_subnets"]').addClass('readonly');
        }
    });

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
