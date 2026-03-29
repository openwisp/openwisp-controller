from django.dispatch import Signal

notify = Signal()
notify.__doc__ = """
Creates notification(s).

Sends arguments: 'recipient', 'actor', 'verb', 'action_object',
    'target', 'description', 'timestamp', 'level', 'type', etc.
"""
