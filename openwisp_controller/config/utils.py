import copy
import logging
import time

import shortuuid
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404 as base_get_object_or_404
from django.urls import path
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.signals import notify
from openwisp_notifications.utils import _get_object_link

from openwisp_controller.config import settings as app_settings

logger = logging.getLogger(__name__)


def get_object_or_404(model, **kwargs):
    """
    like ``django.shortcuts.get_object_or_404``
    but handles eventual exceptions caused by
    malformed UUIDs (raising an ``Http404`` exception)
    """
    try:
        return base_get_object_or_404(model, **kwargs)
    except ValidationError:
        raise Http404()


class ControllerResponse(HttpResponse):
    """
    extends ``django.http.HttpResponse`` by adding a custom HTTP header
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self["X-Openwisp-Controller"] = "true"


def send_file(filename, contents):
    """
    returns a ``ControllerResponse`` object with an attachment
    """
    response = ControllerResponse(contents, content_type="application/octet-stream")
    response["Content-Disposition"] = "attachment; filename={0}".format(filename)
    return response


def send_device_config(config, request):
    """
    calls ``update_last_ip`` and returns a ``ControllerResponse``
    which includes the configuration tar.gz as attachment
    """
    update_last_ip(config.device, request)
    return send_file(
        filename="{0}.tar.gz".format(config.name), contents=config.generate().getvalue()
    )


def send_vpn_config(vpn, request):
    """
    returns a ``ControllerResponse``which includes the configuration
    tar.gz as attachment
    """
    return send_file(
        filename="{0}.tar.gz".format(vpn.name),
        contents=vpn.get_cached_configuration().getvalue(),
    )


def update_last_ip(device, request):
    """
    updates ``last_ip`` if necessary
    """
    ip = request.META.get("REMOTE_ADDR")
    management_ip = request.GET.get("management_ip")
    update_fields = []

    if device.last_ip != ip:
        device.last_ip = ip
        update_fields.append("last_ip")
    if device.management_ip != management_ip:
        device.management_ip = management_ip
        update_fields.append("management_ip")
    if update_fields:
        device.save(update_fields=update_fields)

    return bool(update_fields)


def generate_common_name(device):
    """
    Returns a unique common name for a device certificate.
    """
    end = 63 - len(device.mac_address)
    truncated_name = device.name[:end]
    unique_slug = shortuuid.ShortUUID().random(length=8)
    cn_format = app_settings.COMMON_NAME_FORMAT
    if cn_format == "{mac_address}-{name}" and truncated_name == device.mac_address:
        cn_format = "{mac_address}"
    format_dict = {**device.__dict__, "name": truncated_name}
    common_name = cn_format.format(**format_dict)[:55]
    common_name = f"{common_name}-{unique_slug}"
    return common_name


DEFAULT_CLIENT_EXTENSIONS = [
    {"name": "nsCertType", "value": "client", "critical": False}
]


def copy_ca_attributes(ca, blueprint=None):
    """
    Extracts base X.509 attributes (such as key length, digest, and
    location data) from the provided CA or blueprint certificate.
    """
    source = blueprint or ca
    digest = str(source.digest)
    return dict(
        key_length=source.key_length,
        digest=digest,
        country_code=source.country_code,
        state=source.state,
        city=source.city,
        organization_name=source.organization_name,
        organizational_unit_name=source.organizational_unit_name,
        email=source.email,
    )


def get_client_extensions(blueprint=None, hardware_oids=None):
    """
    Compiles the list of X.509 extensions for a new client certificate.
    """
    if blueprint and blueprint.extensions:
        extensions = copy.deepcopy(blueprint.extensions)
    else:
        extensions = list(DEFAULT_CLIENT_EXTENSIONS)
    if hardware_oids:
        extensions.extend(hardware_oids)
    return extensions


def revoke_device_cert(instance):
    """
    Revokes the certificate of a VPN client or device certificate
    instance if it exists and was auto-provisioned.
    """
    try:
        if instance.cert and instance.auto_cert:
            instance.cert.revoke()
    except ObjectDoesNotExist:
        pass


def forbid_unallowed(request, param_group, param, allowed_values=None):
    """
    checks for malformed requests - eg: missing parameters (HTTP 400)
    or unauthorized requests - eg: wrong key (HTTP 403)
    if the request is legitimate, returns ``None``
    otherwise calls ``invalid_response``
    """
    error = None
    value = getattr(request, param_group).get(param)
    if not value:
        error = 'error: missing required parameter "{}"\n'.format(param)
        return invalid_response(request, error, status=400)
    if allowed_values and not isinstance(allowed_values, list):
        allowed_values = [allowed_values]
    if allowed_values is not None and value not in allowed_values:
        error = "error: wrong {}\n".format(param)
        return invalid_response(request, error, status=403)


def invalid_response(request, error, status, content_type="text/plain"):
    """
    logs an invalid request and returns a ``ControllerResponse``
    with the specified HTTP status code, which defaults to 403
    """
    logger.warning(error, extra={"request": request, "stack": True})
    return ControllerResponse(error, content_type=content_type, status=status)


def get_controller_urls(views_module):
    """
    used by third party apps to reduce boilerplate
    """
    urls = [
        path(
            "controller/device/checksum/<uuid_any:pk>/",
            views_module.device_checksum,
            name="device_checksum",
        ),
        path(
            "controller/device/download-config/<uuid_any:pk>/",
            views_module.device_download_config,
            name="device_download_config",
        ),
        path(
            "controller/device/update-info/<uuid_any:pk>/",
            views_module.device_update_info,
            name="device_update_info",
        ),
        path(
            "controller/device/report-status/<uuid_any:pk>/",
            views_module.device_report_status,
            name="device_report_status",
        ),
        path(
            "controller/device/register/",
            views_module.device_register,
            name="device_register",
        ),
        path(
            "controller/vpn/checksum/<uuid_any:pk>/",
            views_module.vpn_checksum,
            name="vpn_checksum",
        ),
        path(
            "controller/vpn/download-config/<uuid_any:pk>/",
            views_module.vpn_download_config,
            name="vpn_download_config",
        ),
        # legacy URLs
        path(
            "controller/checksum/<uuid_any:pk>/",
            views_module.device_checksum,
            name="checksum_legacy",
        ),
        path(
            "controller/download-config/<uuid_any:pk>/",
            views_module.device_download_config,
            name="download_config_legacy",
        ),
        path(
            "controller/update-info/<uuid_any:pk>/",
            views_module.device_update_info,
            name="update_info_legacy",
        ),
        path(
            "controller/report-status/<uuid_any:pk>/",
            views_module.device_report_status,
            name="report_status_legacy",
        ),
        path(
            "controller/register/",
            views_module.device_register,
            name="register_legacy",
        ),
    ]
    return urls


def get_default_templates_queryset(
    organization_id, backend=None, queryset=None, model=None
):
    """
    Adds organization filtering to default template queryset:
        filter only templates belonging to same organization
        or shared templates (with organization=None)
    This function is used in:
        * openwisp_controller.config.Template.get_default_templates
        * openwisp_controller.config.views.get_default_templates
    """
    if queryset is None:
        queryset = model.objects.filter(default=True)
    if organization_id:
        queryset = queryset.filter(
            Q(organization_id=organization_id) | Q(organization_id=None)
        ).order_by("-required", "name")
    if backend:
        queryset = queryset.filter(backend=backend)
    return queryset


def get_config_error_notification_target_url(obj, field, absolute_url=True):
    url = _get_object_link(obj._related_object(field), absolute_url)
    return f"{url}#config-group"


def send_api_task_notification(type, sleep_time=False, **kwargs):
    """
    The sleep_time argument is needed to avoid triggering the toast
    notification in the admin while the page is reloading.
    """
    if sleep_time:
        time.sleep(sleep_time)
    vpn = kwargs.get("instance")
    action = kwargs.get("action", "").replace("_", " ")
    exception = kwargs.get("exception")
    message_map = {
        "error": {
            "verb": _("encountered an unrecoverable error"),
            "message": _(
                "Unable to perform {action} operation on the "
                "{target} VPN server due to an "
                "unrecoverable error "
                "({error_type})"
            ),
            "level": "error",
        },
        "success": {
            "verb": _("has been completed successfully"),
            "message": _("The {action} operation on {target} {verb}."),
            "level": "info",
        },
    }
    meta = message_map[type]
    notify.send(
        sender=vpn,
        target=vpn,
        type="generic_message",
        action_object=vpn,
        verb=meta["verb"],
        message=meta["message"].format(
            action=action,
            target=str(vpn),
            error_type=exception.__class__.__name__ if exception else "",
            verb=meta["verb"],
        ),
        description=str(exception) if exception else "",
        level=meta["level"],
    )


def handle_recovery_notification(task_key, sleep_time=False, **kwargs):
    task_result = cache.get(task_key)
    if task_result == "error":
        send_api_task_notification("success", sleep_time=sleep_time, **kwargs)
    cache.set(task_key, "success", timeout=None)


def handle_error_notification(task_key, sleep_time=False, **kwargs):
    cached_value = cache.get(task_key)
    if cached_value != "error":
        cache.set(task_key, "error", timeout=None)
        send_api_task_notification("error", sleep_time=sleep_time, **kwargs)
