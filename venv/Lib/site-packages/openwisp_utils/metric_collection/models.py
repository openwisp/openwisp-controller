import logging

from django.db import models
from django.utils.translation import gettext_lazy as _
from packaging.version import parse as parse_version

from ..admin_theme.system_info import (
    get_enabled_openwisp_modules,
    get_openwisp_installation_method,
    get_openwisp_version,
    get_os_details,
)
from ..base import TimeStampedEditableModel
from .helper import COLLECTOR_URL, get_events, post_metrics

logger = logging.getLogger(__name__)


class OpenwispVersion(TimeStampedEditableModel):
    modified = None
    module_version = models.JSONField(default=dict, blank=True)

    # DEPRECATED: Use COLLECTOR_URL from helper module instead.
    # TODO: Remove this in the next major release.
    COLLECTOR_URL = COLLECTOR_URL

    class Meta:
        ordering = ("-created",)

    @classmethod
    def log_module_version_changes(cls, current_versions):
        """Logs changes to the version of installed OpenWISP modules.

        Returns a tuple of booleans indicating:

        - whether this is a new installation
        - whether any OpenWISP modules has been upgraded.

        If no module has been upgraded, it won't store anything in the DB.
        """
        openwisp_version = cls.objects.first()
        if not openwisp_version:
            # If no OpenwispVersion object is present,
            # it means that this is a new installation and
            # we don't need to check for upgraded modules.
            cls.objects.create(module_version=current_versions)
            return True, False
        # Check which installed modules have been upgraded by comparing
        # the currently installed versions in current_versions with the
        # versions stored in the OpenwispVersion object. The return value
        # is a dictionary of module:version pairs that have been upgraded.
        old_versions = openwisp_version.module_version
        upgraded_modules = {}
        for module, version in current_versions.items():
            # The OS version does not follow semver,
            # therefore it's handled differently.
            if module in ["kernel_version", "os_version", "hardware_platform"]:
                if old_versions.get(module) != version:
                    upgraded_modules[module] = version
            elif (
                # Check if a new OpenWISP module was enabled
                # on an existing installation
                module not in old_versions
                or (
                    # Check if an OpenWISP module was upgraded
                    module in old_versions
                    and parse_version(old_versions[module]) < parse_version(version)
                )
            ):
                upgraded_modules[module] = version
            openwisp_version.module_version[module] = version
        # Log version changes
        if upgraded_modules:
            OpenwispVersion.objects.create(module_version=current_versions)
            return False, True
        return False, False

    @classmethod
    def send_usage_metrics(cls, category):
        consent_obj = Consent.objects.first()
        if consent_obj and not consent_obj.user_consented:
            return
        assert category in ["Install", "Heartbeat", "Upgrade"]

        current_versions = get_enabled_openwisp_modules()
        current_versions.update({"OpenWISP Version": get_openwisp_version()})
        current_versions.update(get_os_details())
        is_install, is_upgrade = OpenwispVersion.log_module_version_changes(
            current_versions
        )

        # Handle special conditions when the user forgot to execute the migrate
        # command, and an install or upgrade operation is detected in the
        # Heartbeat event. In this situation, we override the category.
        if category == "Heartbeat":
            if is_install:
                category = "Install"
            if is_upgrade:
                category = "Upgrade"
        elif category == "Upgrade" and not is_upgrade:
            # The task was triggered with "Upgrade" category, but no
            # upgrades were detected in the OpenWISP module versions.
            # This occurs when the migrate command is executed but
            # no OpenWISP python module was upgraded.
            # We don't count these as upgrades.
            return
        elif category == "Install" and not is_install:
            # Similar to above, but for "Install" category
            return

        metrics = get_events(category, current_versions)
        metrics.extend(
            get_events(
                category, {"Installation Method": get_openwisp_installation_method()}
            )
        )
        logger.info(f"Sending metrics, category={category}")
        post_metrics(metrics)
        logger.info(f"Metrics sent successfully, category={category}")
        logger.info(f"Metrics: {metrics}")


class Consent(TimeStampedEditableModel):
    """Stores consent to collect anonymous usage metrics.

    The ``shown_once`` field is used to track whether the info message
    about the metric collection has been shown to the superuser on their
    first login. The ``user_consented`` field stores whether the superuser
    has opted-out of collecting anonymous usage metrics.
    """

    shown_once = models.BooleanField(
        default=False,
    )
    # Metric collection is opt-out. By default, metric collection is enabled.
    # Disabling it is a one-time action by the superuser. Whenever a superuser
    # disables metric collection, they are opting-out to share anymore anonymous
    # usage metrics with the OpenWISP project.
    user_consented = models.BooleanField(
        default=True,
        verbose_name=_(
            "Help improve OpenWISP by allowing the "
            "collection of anonymous usage metrics."
        ),
        help_text=_(
            "These statistics help us prioritize features, "
            " fix bugs, and better support real-world usage,"
            " all without collecting any personal data. "
            '<a href="https://openwisp.io/docs/user/usage-metric-collection.html"'
            ' target="_blank">Learn more about why we collect metrics</a>.'
        ),
    )

    @classmethod
    def update_consent_withdrawal(cls, sender, instance, **kwargs):
        """Collects metric when a user withdraws consent for metric collection.

        This signal handler sends a 'Consent Withdrawn' event when a user
        changes user_consented from True to False, providing the last data
        point before communications are interrupted.
        """
        if instance._state.adding or instance.user_consented is True:
            # This is a new instance or the user has not opted out,
            return

        try:
            db_instance = sender.objects.get(pk=instance.pk)
            # Check if consent was withdrawn (changed from True to False)
            if (
                instance.user_consented is False
                and db_instance.user_consented != instance.user_consented
            ):
                logger.info("Consent withdrawn, sending final metric event")
                # Create a simple event for consent withdrawal
                events = get_events("Consent Withdrawn", {"Action": "Opt-out"})
                post_metrics(events)
                logger.info("Consent withdrawal metric sent successfully")
        except sender.DoesNotExist:
            # In case the instance doesn't exist in DB yet, just pass
            pass
