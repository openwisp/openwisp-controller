from django.test import SimpleTestCase

from openwisp_controller.config.converters import UUIDAnyConverter


class TestUUIDConverters(SimpleTestCase):
    def test_uuid_any_converter_dashed(self):
        converter = UUIDAnyConverter()
        valid_uuid = "de8fa775-1134-47b6-adc5-2da3d0626c72"
        self.assertEqual(converter.to_python(valid_uuid), valid_uuid)

    def test_uuid_any_converter_hex(self):
        converter = UUIDAnyConverter()
        hex_uuid = "de8fa775113447b6adc52da3d0626c72"
        expected = "de8fa775-1134-47b6-adc5-2da3d0626c72"
        self.assertEqual(converter.to_python(hex_uuid), expected)

    def test_uuid_any_converter_invalid(self):
        converter = UUIDAnyConverter()
        with self.assertRaises(ValueError):
            converter.to_python("not-a-uuid")

    def test_uuid_any_converter_uppercase(self):
        converter = UUIDAnyConverter()
        uppercase_uuid = "DE8FA775-1134-47B6-ADC5-2DA3D0626C72"
        with self.assertRaises(ValueError):
            converter.to_python(uppercase_uuid)
