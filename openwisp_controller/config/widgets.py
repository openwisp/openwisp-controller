from django import forms
from django.contrib.admin.widgets import AdminTextareaWidget
from django.template.loader import get_template
from django.urls import reverse
from swapper import load_model

DeviceGroup = load_model('config', 'DeviceGroup')


class JsonSchemaWidget(AdminTextareaWidget):
    """
    JSON Schema Editor widget
    """

    schema_view_name = 'config:schema'
    netjsonconfig_hint = True
    extra_attrs = {}
    advanced_mode = True

    @property
    def media(self):
        js = [
            'config/js/lib/advanced-mode.js',
            'config/js/lib/tomorrow_night_bright.js',
            'config/js/lib/jsonschema-ui.js',
            'admin/js/jquery.init.js',
            'config/js/widget.js',
            'config/js/utils.js',
        ]
        css = {
            'all': [
                f'config/css/{path}'
                for path in ('lib/jsonschema-ui.css', 'lib/advanced-mode.css')
            ]
        }
        return forms.Media(js=js, css=css)

    def render(self, name, value, attrs=None, renderer=None):
        template = get_template('admin/config/jsonschema-widget.html')
        context = {
            'netjsonconfig_hint': self.netjsonconfig_hint,
            'advanced_mode': self.advanced_mode,
        }
        attrs = attrs or {}
        attrs['class'] = 'vLargeTextField jsoneditor-raw {}'.format(
            self.extra_attrs.get('class')
        )
        attrs.update(self.extra_attrs)
        if self.schema_view_name:
            context['schema_view_name'] = self.schema_view_name
            attrs.update({'data-schema-url': reverse(self.schema_view_name)})
        html = template.render(context)
        html += super().render(name, value, attrs, renderer)
        return html


class DeviceGroupJsonSchemaWidget(JsonSchemaWidget):
    schema_view_name = (
        f'admin:{DeviceGroup._meta.app_label}_{DeviceGroup._meta.model_name}_schema'
    )
    app_label_model = f'{DeviceGroup._meta.app_label}_{DeviceGroup._meta.model_name}'
    netjsonconfig_hint = False
    advanced_mode = False
    extra_attrs = {}

    @property
    def media(self):
        return super().media + forms.Media(css={'all': ['config/css/devicegroup.css']})
