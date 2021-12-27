import logging

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404 as base_get_object_or_404
from django.urls import path, re_path

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
    update_fields = []

    if device.last_ip != ip:
        device.last_ip = ip
        update_fields.append('last_ip')
    if device.management_ip != management_ip:
        device.management_ip = management_ip
        update_fields.append('management_ip')
    if update_fields:
        device.save(update_fields=update_fields)

    return bool(update_fields)


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
        re_path(
            'controller/device/checksum/(?P<pk>[^/]+)/$',
            views_module.device_checksum,
            name='device_checksum',
        ),
        re_path(
            'controller/device/download-config/(?P<pk>[^/]+)/$',
            views_module.device_download_config,
            name='device_download_config',
        ),
        re_path(
            'controller/device/update-info/(?P<pk>[^/]+)/$',
            views_module.device_update_info,
            name='device_update_info',
        ),
        re_path(
            'controller/device/report-status/(?P<pk>[^/]+)/$',
            views_module.device_report_status,
            name='device_report_status',
        ),
        path(
            'controller/device/register/',
            views_module.device_register,
            name='device_register',
        ),
        re_path(
            'controller/vpn/checksum/(?P<pk>[^/]+)/$',
            views_module.vpn_checksum,
            name='vpn_checksum',
        ),
        re_path(
            'controller/vpn/download-config/(?P<pk>[^/]+)/$',
            views_module.vpn_download_config,
            name='vpn_download_config',
        ),
        # legacy URLs
        re_path(
            'controller/checksum/(?P<pk>[^/]+)/$',
            views_module.device_checksum,
            name='checksum_legacy',
        ),
        re_path(
            'controller/download-config/(?P<pk>[^/]+)/$',
            views_module.device_download_config,
            name='download_config_legacy',
        ),
        re_path(
            'controller/update-info/(?P<pk>[^/]+)/$',
            views_module.device_update_info,
            name='update_info_legacy',
        ),
        re_path(
            'controller/report-status/(?P<pk>[^/]+)/$',
            views_module.device_report_status,
            name='report_status_legacy',
        ),
        path(
            'controller/register/',
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
    if organization_id:
        queryset = queryset.filter(
            Q(organization_id=organization_id) | Q(organization_id=None)
        ).order_by('-required', 'name')
    if backend:
        queryset = queryset.filter(backend=backend)
    return queryset
