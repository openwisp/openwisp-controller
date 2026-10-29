import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import connection
from django.db.models.signals import post_migrate
from django.test import TransactionTestCase

from .utils import ControllerLiveServerTestCase


class FakeDaphneProcess:
    def __init__(self, *args, **kwargs):
        self.ready = Event()
        self.port = SimpleNamespace(value=12345)
        self.running = False
        self.joined = False

    def start(self):
        self.content_types = list(
            ContentType.objects.order_by("pk").values_list("pk", "app_label", "model")
        )
        self.site_id = Site.objects.get_current().pk
        self.running = True
        self.ready.set()

    def is_alive(self):
        return self.running

    def terminate(self):
        self.running = False

    def join(self):
        self.joined = True


class TestLiveServerLifecycle(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(
            patch.object(
                connection,
                "_test_serialized_contents",
                connection.creation.serialize_db_to_string(),
                create=True,
            )
        )

    def test_mixed_classes(self):
        """Run both class orders without recreating the database between them."""
        expected_content_types = list(
            ContentType.objects.order_by("pk").values_list("pk", "app_label", "model")
        )

        class OrdinaryTest(TransactionTestCase):
            def test_defaults(self):
                self.assertTrue(Site.objects.filter(pk=settings.SITE_ID).exists())
                self.assertTrue(Permission.objects.exists())
                self.assertFalse(
                    Site.objects.filter(domain="browser-created.example").exists()
                )

        class BrowserTest(ControllerLiveServerTestCase):
            ProtocolServerProcess = FakeDaphneProcess

            @staticmethod
            def _is_in_memory_db(connection):
                # The fixture test uses a fake process, not a live server.
                return False

            def _check_fixtures(self):
                current = list(
                    ContentType.objects.order_by("pk").values_list(
                        "pk", "app_label", "model"
                    )
                )
                self.assertEqual(current, expected_content_types)
                self.assertEqual(current, self._server_process.content_types)
                self.assertEqual(
                    Site.objects.get_current().pk, self._server_process.site_id
                )
                self.assertFalse(
                    Site.objects.filter(domain="browser-created.example").exists()
                )
                Site.objects.create(domain="browser-created.example", name="Test row")

            def test_first(self):
                self._check_fixtures()

            def test_second(self):
                self._check_fixtures()

        class SecondBrowserTest(BrowserTest):
            pass

        suite = unittest.TestSuite(
            [
                OrdinaryTest("test_defaults"),
                BrowserTest("test_first"),
                BrowserTest("test_second"),
                OrdinaryTest("test_defaults"),
                SecondBrowserTest("test_first"),
                SecondBrowserTest("test_second"),
                OrdinaryTest("test_defaults"),
            ]
        )
        result = unittest.TestResult()
        suite.run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertEqual(result.testsRun, 7)
        for cls in (BrowserTest, SecondBrowserTest):
            self.assertFalse(cls._server_process.is_alive())
            self.assertTrue(cls._server_process.joined)

    def test_failed_setup_cleanup(self):
        """Stop partial server startup before restoring ordinary test defaults."""
        events = []

        class Process(FakeDaphneProcess):
            def terminate(self):
                events.append("stopped")
                super().terminate()

        class FailedStartProcess(Process):
            def start(self):
                super().start()
                raise RuntimeError("Simulated server startup failure")

        class BrowserTest(ControllerLiveServerTestCase):
            ProtocolServerProcess = FailedStartProcess

            @staticmethod
            def _is_in_memory_db(connection):
                return False

            def test_unused(self):
                self.fail("A failed class setup must not run its tests")

        class FailedSubclassSetup(BrowserTest):
            ProtocolServerProcess = Process

            @classmethod
            def setUpClass(cls):
                super().setUpClass()
                raise RuntimeError("Simulated WebDriver startup failure")

        def migrated(**kwargs):
            events.append("migrated")

        post_migrate.connect(migrated)
        self.addCleanup(post_migrate.disconnect, migrated)
        allowed_hosts = list(settings.ALLOWED_HOSTS)
        for cls in (BrowserTest, FailedSubclassSetup):
            with self.subTest(stage=cls.__name__):
                events.clear()
                result = unittest.TestResult()
                unittest.TestSuite([cls("test_unused")]).run(result)
                self.assertEqual(len(result.errors), 1)
                self.assertIn("Simulated", result.errors[0][1])
                self.assertEqual(result.testsRun, 0)
                self.assertFalse(cls._server_process.is_alive())
                self.assertTrue(cls._server_process.joined)
                self.assertLess(events.index("stopped"), events.index("migrated"))
                self.assertTrue(Site.objects.filter(pk=settings.SITE_ID).exists())
                self.assertTrue(Permission.objects.exists())
                self.assertEqual(settings.ALLOWED_HOSTS, allowed_hosts)
