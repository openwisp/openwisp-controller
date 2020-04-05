from django.dispatch import Signal

config_modified = Signal(providing_args=['device', 'config'])
