from django.dispatch import Signal

subnet_provisioned = Signal(providing_args=['instance', 'provisioned'])
