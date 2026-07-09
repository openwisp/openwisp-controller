from django.dispatch import Signal

is_working_changed = Signal()
is_working_changed.__doc__ = """
Providing araguments: [
    'is_working',
    'old_is_working',
    'instance',
    'failure_reason',
    'old_failure_reason'
]
"""
