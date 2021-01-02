import logging

from django.conf.urls import url
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404 as base_get_object_or_404

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
        self['X-Openwisp-Controller'] = 'true'


def send_file(filename, contents):
    """
    returns a ``ControllerResponse`` object with an attachment
    """
    response = ControllerResponse(contents, content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
    return response


def send_device_config(config, request):
    """
    calls ``update_last_ip`` and returns a ``ControllerResponse``
    which includes the configuration tar.gz as attachment
    """
    update_last_ip(config.device, request)
    return send_file(
        filename='{0}.tar.gz'.format(config.name), contents=config.generate().getvalue()
    )


def send_vpn_config(vpn, request):
    """
    returns a ``ControllerResponse``which includes the configuration
    tar.gz as attachment
    """
    return send_file(
        filename='{0}.tar.gz'.format(vpn.name), contents=vpn.generate().getvalue()
    )


def update_last_ip(device, request):
    """
    updates ``last_ip`` if necessary
    """
    ip = request.META.get('REMOTE_ADDR')
    management_ip = request.GET.get('management_ip')
    changed = False
    if device.last_ip != ip:
        device.last_ip = ip
        changed = True
    if device.management_ip != management_ip:
        device.management_ip = management_ip
        changed = True
    if changed:
        device.save()
    return changed


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
        error = 'error: wrong {}\n'.format(param)
        return invalid_response(request, error, status=403)


def invalid_response(request, error, status, content_type='text/plain'):
    """
    logs an invalid request and returns a ``ControllerResponse``
    with the specified HTTP status code, which defaults to 403
    """
    logger.warning(error, extra={'request': request, 'stack': True})
    return ControllerResponse(error, content_type=content_type, status=status)


def get_controller_urls(views_module):
    """
    used by third party apps to reduce boilerplate
    """
    urls = [
        url(
            r'^controller/device/checksum/(?P<pk>[^/]+)/$',
            views_module.device_checksum,
            name='device_checksum',
        ),
        url(
            r'^controller/device/download-config/(?P<pk>[^/]+)/$',
            views_module.device_download_config,
            name='device_download_config',
        ),
        url(
            r'^controller/device/update-info/(?P<pk>[^/]+)/$',
            views_module.device_update_info,
            name='device_update_info',
        ),
        url(
            r'^controller/device/report-status/(?P<pk>[^/]+)/$',
            views_module.device_report_status,
            name='device_report_status',
        ),
        url(
            r'^controller/device/register/$',
            views_module.device_register,
            name='device_register',
        ),
        url(
            r'^controller/vpn/checksum/(?P<pk>[^/]+)/$',
            views_module.vpn_checksum,
            name='vpn_checksum',
        ),
        url(
            r'^controller/vpn/download-config/(?P<pk>[^/]+)/$',
            views_module.vpn_download_config,
            name='vpn_download_config',
        ),
        # legacy URLs
        url(
            r'^controller/checksum/(?P<pk>[^/]+)/$',
            views_module.device_checksum,
            name='checksum_legacy',
        ),
        url(
            r'^controller/download-config/(?P<pk>[^/]+)/$',
            views_module.device_download_config,
            name='download_config_legacy',
        ),
        url(
            r'^controller/update-info/(?P<pk>[^/]+)/$',
            views_module.device_update_info,
            name='update_info_legacy',
        ),
        url(
            r'^controller/report-status/(?P<pk>[^/]+)/$',
            views_module.device_report_status,
            name='report_status_legacy',
        ),
        url(
            r'^controller/register/$',
            views_module.device_register,
            name='register_legacy',
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
    queryset = queryset.filter(
        Q(organization_id=organization_id) | Q(organization_id=None)
    )
    if backend:
        queryset = queryset.filter(backend=backend)
    return queryset
