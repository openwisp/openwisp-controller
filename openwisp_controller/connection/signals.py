from django.dispatch import Signal

is_working_changed = Signal(providing_args=['is_working', 'instance'])
