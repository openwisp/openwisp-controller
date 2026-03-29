import logging

from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from ..utils import retryable_request

logger = logging.getLogger(__name__)
COLLECTOR_URL = "https://analytics.openwisp.io/cleaninsights.php"


class MetricCollectionAdminSiteHelper:
    """Collection of helper methods for the OpenWISP Admin Theme

    Designed to be used in the admin_theme to show the constent info
    message and allow superusers to opt out.
    """

    @classmethod
    def is_enabled(cls):
        return "openwisp_utils.metric_collection" in getattr(
            settings, "INSTALLED_APPS", []
        )

    @classmethod
    def is_enabled_and_superuser(cls, user):
        return cls.is_enabled() and user.is_superuser

    @classmethod
    def show_consent_info(cls, request):
        """Consent screen logic

        Unless already shown, this method adds a message (using the Django
        Message Framework) to the request passed in as argument to inform
        the super user about the OpenWISP metric collection feature and
        the possibility to opt out.
        """
        if not cls.is_enabled_and_superuser(request.user):
            return

        consent = cls._get_consent()

        if not consent.shown_once:
            messages.info(
                request,
                mark_safe(
                    _(
                        "<strong>Congratulations for installing "
                        "OpenWISP successfully!</strong><br>"
                        "Use the navigation menu on the left to explore "
                        "the interface and begin deploying your network.<br>"
                        "Keep in mind: we gather anonymous usage "
                        "metrics to improve OpenWISP. "
                        "You can opt out from the "
                        '<a href="{url}">System Information page</a>.'
                    ).format(url=reverse("admin:ow-info"))
                ),
            )
            # Update the field in DB after showing the message for the
            # first time.
            consent._meta.model.objects.update(shown_once=True)

    @classmethod
    def manage_form(cls, request, context):
        if not cls.is_enabled_and_superuser(request.user):
            return

        from .admin import ConsentForm

        consent = cls._get_consent()

        if request.POST:
            form = ConsentForm(request.POST, instance=consent)
            form.full_clean()
            form.save()
        else:
            form = ConsentForm(instance=consent)

        context.update(
            {
                "metric_collection_installed": cls.is_enabled(),
                "metric_consent_form": form,
            }
        )

    @classmethod
    def _get_consent(cls):
        if not cls.is_enabled():
            return None

        from .models import Consent

        consent = Consent.objects.first()
        if not consent:
            consent = Consent.objects.create()
        return consent


def post_metrics(events, collector_url=COLLECTOR_URL):
    """Post metrics events to the Clean Insights collector.

    Args:
        events: List of event dictionaries to send collector_url: URL of
        the Clean Insights collector
    """
    try:
        response = retryable_request(
            "post",
            url=collector_url,
            json={
                "idsite": 5,
                "events": events,
            },
            max_retries=10,
        )
        assert response.status_code == 204
    except Exception as error:
        if isinstance(error, AssertionError):
            message = f"HTTP {response.status_code} Response"
        else:
            message = str(error)
        logger.error(
            f"Collection of usage metrics failed, max retries exceeded. Error: {message}"
        )


def get_events(category, data):
    """Returns a list of events that will be sent to CleanInsights.

    This method requires two input parameters, category and data, which
    represent usage metrics, and returns a list of events in a format
    accepted by the Clean Insights Matomo Proxy (CIMP) API.

    Read the "Event Measurement Schema" in the CIMP documentation:
    https://cutt.ly/SwBkC40A
    """
    events = []
    unix_time = int(now().timestamp())
    for key, value in data.items():
        events.append(
            {
                # OS Details, Install, Hearthbeat, Upgrade, Consent Withdrawn
                "category": category,
                # Name of OW module or OS parameter
                "action": escape(key),
                # Actual version of OW module, OS or general OW version
                "name": escape(value),
                # Value is always 1
                "value": 1,
                # Event happened only 1 time, we do not aggregate
                "times": 1,
                "period_start": unix_time,
                "period_end": unix_time,
            }
        )
    return events
