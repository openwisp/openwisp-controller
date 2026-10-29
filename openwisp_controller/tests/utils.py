import django
from channels.testing import ChannelsLiveServerTestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import connections
from django.urls import reverse

from openwisp_users.tests.utils import TestMultitenantAdminMixin

user_model = get_user_model()

# Keep cache-clearing tests isolated from Redis used by parallel workers.
LOCAL_MEMORY_CACHE = {
    **settings.CACHES,
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "controller-isolated-tests",
    },
}


class ControllerLiveServerTestCase(ChannelsLiveServerTestCase):
    # Preserve migration-created rows and IDs across the Daphne process lifetime.
    serialized_rollback = True

    @classmethod
    def setUpClass(cls):
        cls.databases = cls._validate_databases()
        cls._serialized_databases = [
            alias
            for alias in cls._databases_names(include_mirrors=False)
            if hasattr(connections[alias], "_test_serialized_contents")
        ]
        cls.addClassCleanup(cls._restore_database)
        # Ordinary transaction tests may have recreated content types with new IDs.
        cls._flush_databases(inhibit_post_migrate=True)
        # Django 5.2+ restores the snapshot in the parent's class setup.
        if django.VERSION < (5, 2):
            for alias in cls._serialized_databases:
                connection = connections[alias]
                connection.creation.deserialize_db_from_string(
                    connection._test_serialized_contents
                )
        cls._clear_model_caches()
        try:
            super().setUpClass()
        except BaseException:
            cls._stop_server()
            raise
        # Also runs if a subclass fails after Daphne starts, e.g. opening WebDriver.
        cls.addClassCleanup(cls._stop_server)

    @classmethod
    def _stop_server(cls):
        process = cls.__dict__.get("_server_process")
        if process is not None and process.is_alive():
            process.terminate()
            process.join()
        modified_settings = cls.__dict__.get("_live_server_modified_settings")
        if modified_settings is not None and hasattr(modified_settings, "wrapped"):
            modified_settings.disable()

    @classmethod
    def _restore_database(cls):
        # Daphne must be stopped before restoring defaults for non-browser tests.
        cls._flush_databases(inhibit_post_migrate=False)

    @classmethod
    def _flush_databases(cls, inhibit_post_migrate):
        for alias in cls._serialized_databases:
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=alias,
                reset_sequences=False,
                inhibit_post_migrate=inhibit_post_migrate,
            )
        cls._clear_model_caches()

    @staticmethod
    def _clear_model_caches():
        ContentType.objects.clear_cache()
        Site.objects.clear_cache()


class TestAdminMixin(TestMultitenantAdminMixin):
    def _test_changelist_recover_deleted(self, app_label, model_label):
        self._test_multitenant_admin(
            url=reverse("admin:{0}_{1}_changelist".format(app_label, model_label)),
            visible=[],
            hidden=[],
        )

    def _login(self, username="admin", password="tester"):
        self.client.force_login(user_model.objects.get(username=username))
