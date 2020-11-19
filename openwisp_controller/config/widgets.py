from django import forms
from django.contrib.admin.widgets import AdminTextareaWidget
from django.template.loader import get_template


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
            f'config/js/{path}'
            for path in (
                'utils.js',
                'lib/advanced-mode.js',
                'lib/tomorrow_night_bright.js',
                'lib/jsonschema-ui.js',
                'widget.js',
            )
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
        html = template.render(
            {
                'schema_view_name': self.schema_view_name,
                'netjsonconfig_hint': self.netjsonconfig_hint,
                'advanced_mode': self.advanced_mode,
            }
        )
        attrs = attrs or {}
        attrs['class'] = 'vLargeTextField jsoneditor-raw'
        attrs.update(self.extra_attrs)
        html += super().render(name, value, attrs, renderer)
        return html
