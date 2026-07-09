from django.dispatch import Signal

subnet_provisioned = Signal()
subnet_provisioned.__doc__ = """
Providing arguments: ['instance', 'provisioned']
"""
