"""Auto-generated file, do not edit by hand. BJ metadata"""
from ..phonemetadata import NumberFormat, PhoneNumberDesc, PhoneMetadata

PHONE_METADATA_BJ = PhoneMetadata(id='BJ', country_code=229, international_prefix='00',
    general_desc=PhoneNumberDesc(national_number_pattern='(?:01\\d|8)\\d{7}', possible_length=(8, 10)),
    fixed_line=PhoneNumberDesc(national_number_pattern='012\\d{7}', example_number='0120211234', possible_length=(10,)),
    mobile=PhoneNumberDesc(national_number_pattern='01(?:2[5-9]|[4-69]\\d)\\d{6}', example_number='0195123456', possible_length=(10,)),
    voip=PhoneNumberDesc(national_number_pattern='857[58]\\d{4}', example_number='85751234', possible_length=(8,)),
    uan=PhoneNumberDesc(national_number_pattern='81\\d{6}', example_number='81123456', possible_length=(8,)),
    number_format=[NumberFormat(pattern='(\\d{2})(\\d{2})(\\d{2})(\\d{2})', format='\\1 \\2 \\3 \\4', leading_digits_pattern=['8']),
        NumberFormat(pattern='(\\d{2})(\\d{2})(\\d{2})(\\d{2})(\\d{2})', format='\\1 \\2 \\3 \\4 \\5', leading_digits_pattern=['0'])],
    mobile_number_portable_region=True)
