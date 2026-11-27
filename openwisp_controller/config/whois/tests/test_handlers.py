from unittest.mock import patch

from django.dispatch import Signal
from django.test import SimpleTestCase

from .. import handlers


class TestWHOISHandlers(SimpleTestCase):
    def test_override_restores_each_receiver(self):
        signal = Signal()
        sender = object()

        def connected(**kwargs):
            return "connected"

        def disconnected(**kwargs):
            return "disconnected"

        def unrelated(**kwargs):
            return "unrelated"

        signal.connect(connected, sender=sender, dispatch_uid="connected")
        signal.connect(unrelated, sender=sender)
        registrations = (
            (signal, connected, sender, "connected"),
            (signal, disconnected, sender, "disconnected"),
        )
        self.enterContext(
            patch.object(handlers, "_whois_receivers", return_value=registrations)
        )

        def active_receivers():
            return {result for _, result in signal.send(sender=sender)}

        with self.subTest("enable both receivers until normal exit"):
            with handlers.override_whois_handlers(True):
                self.assertEqual(
                    active_receivers(), {"connected", "disconnected", "unrelated"}
                )
            self.assertEqual(active_receivers(), {"connected", "unrelated"})

        with self.subTest("disable both receivers until exceptional exit"):
            with self.assertRaisesMessage(RuntimeError, "failed startup"):
                with handlers.override_whois_handlers(False):
                    self.assertEqual(active_receivers(), {"unrelated"})
                    signal.connect(
                        disconnected, sender=sender, dispatch_uid="disconnected"
                    )
                    self.assertEqual(active_receivers(), {"disconnected", "unrelated"})
                    raise RuntimeError("failed startup")
            self.assertEqual(active_receivers(), {"connected", "unrelated"})
