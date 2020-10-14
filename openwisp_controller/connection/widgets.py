import swapper
from django import forms

from ..config.widgets import JsonSchemaWidget as BaseJsonSchemaWidget

Credentials = swapper.load_model('connection', 'Credentials')
Command = swapper.load_model('connection', 'Command')
app_label = Credentials._meta.app_label
model_name = Credentials._meta.model_name


class CredentialsSchemaWidget(BaseJsonSchemaWidget):
    schema_view_name = f'admin:{app_label}_{model_name}_schema'
    netjsonconfig_hint = False
    advanced_mode = False
    extra_attrs = {'data-schema-selector': '#id_connector'}

    @property
    def media(self):
        media = super().media
        js = ['admin/js/jquery.init.js', 'connection/js/credentials.js'] + list(
            media._js
        )
        css = media._css.copy()
        css['all'] += ['connection/css/credentials.css']
        return forms.Media(js=js, css=css)


class CommandSchemaWidget(BaseJsonSchemaWidget):
    schema_view_name = (
        f'admin:{Command._meta.app_label}_{Command._meta.model_name}_schema'
    )

    app_label_model = f'{Command._meta.app_label}_{Command._meta.model_name}'
    netjsonconfig_hint = False
    advanced_mode = False
    extra_attrs = {
        'data-schema-selector': '#id_command_set-0-type',
        'data-show-errors': 'never',
    }

    @property
    def media(self):
        media = super().media
        js = [
            'admin/js/jquery.init.js',
            'connection/js/lib/reconnecting-websocket.min.js',
            'connection/js/commands.js',
        ] + list(media._js)
        css = media._css.copy()
        css['all'] += ['connection/css/command-inline.css']
        return forms.Media(js=js, css=css)
