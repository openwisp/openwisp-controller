"""Auto-generated file, do not edit by hand. PM metadata"""
from ..phonemetadata import NumberFormat, PhoneNumberDesc, PhoneMetadata

PHONE_METADATA_PM = PhoneMetadata(id='PM', country_code=508, international_prefix='00',
    general_desc=PhoneNumberDesc(national_number_pattern='[78]\\d{8}|[2-9]\\d{5}', possible_length=(6, 9)),
    fixed_line=PhoneNumberDesc(national_number_pattern='80[6-9]\\d{6}|(?:[236-9]\\d|4[1-35-9]|5[0-47-9])\\d{4}', example_number='430123', possible_length=(6, 9)),
    mobile=PhoneNumberDesc(national_number_pattern='708(?:4[0-5]|5[0-6])\\d{4}|(?:[236-9]\\d|4[02-489]|5[02-9])\\d{4}', example_number='551234', possible_length=(6, 9)),
    toll_free=PhoneNumberDesc(national_number_pattern='80[0-5]\\d{6}', example_number='800012345', possible_length=(9,)),
    premium_rate=PhoneNumberDesc(national_number_pattern='8[129]\\d{7}', example_number='810123456', possible_length=(9,)),
    national_prefix='0',
    national_prefix_for_parsing='0',
    number_format=[NumberFormat(pattern='(\\d{2})(\\d{2})(\\d{2})', format='\\1 \\2 \\3', leading_digits_pattern=['[2-9]'], national_prefix_formatting_rule='0\\1'),
        NumberFormat(pattern='(\\d{3})(\\d{3})(\\d{3})', format='\\1 \\2 \\3', leading_digits_pattern=['7']),
        NumberFormat(pattern='(\\d{3})(\\d{2})(\\d{2})(\\d{2})', format='\\1 \\2 \\3 \\4', leading_digits_pattern=['8'], national_prefix_formatting_rule='0\\1')])
