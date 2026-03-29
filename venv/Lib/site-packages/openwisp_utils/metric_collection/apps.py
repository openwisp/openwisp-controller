from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate, pre_save


class MetricsCollectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "openwisp_utils.metric_collection"
    app_label = "openwisp_metric_collection"

    def ready(self):
        super().ready()
        self.connect_signals()

    def connect_signals(self):
        from .models import Consent

        post_migrate.connect(self.post_migrate_receiver, sender=self)
        pre_save.connect(
            Consent.update_consent_withdrawal,
            sender=Consent,
            dispatch_uid=".Consent.update_consent_withdrawal",
        )

    def connect_post_migrate_signal(self):
        """DEPRECATED: Use `connect_signals` instead.

        TODO: Remove this method in the next major release.
        """
        return self.connect_signals()

    @classmethod
    def post_migrate_receiver(cls, **kwargs):
        if getattr(settings, "DEBUG", False):
            # Do not send usage metrics in debug mode.
            # This prevents sending metrics from development setups.
            return

        from .tasks import send_usage_metrics

        is_new_install = False
        if kwargs.get("plan"):
            migration, migration_rolled_back = kwargs["plan"][0]
            # If the migration plan includes creating table
            # for the ContentType model, then the installation is
            # treated as a new installation because that is the
            # first database table created by Django.
            is_new_install = (
                migration_rolled_back is False
                and str(migration) == "contenttypes.0001_initial"
            )

        if is_new_install:
            send_usage_metrics.delay(category="Install")
        else:
            send_usage_metrics.delay(category="Upgrade")
