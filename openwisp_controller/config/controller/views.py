import json
import logging
import uuid
from ipaddress import ip_address

from cache_memoize import cache_memoize
from django.core.cache import cache
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectMixin
from swapper import load_model

from .. import settings as app_settings
from ..signals import checksum_requested, config_download_requested, device_registered
from ..utils import (
    ControllerResponse,
    forbid_unallowed,
    get_object_or_404,
    invalid_response,
    send_device_config,
    send_vpn_config,
    update_last_ip,
)

Device = load_model('config', 'Device')
Config = load_model('config', 'Config')
OrganizationConfigSettings = load_model('config', 'OrganizationConfigSettings')
Vpn = load_model('config', 'Vpn')

logger = logging.getLogger(__name__)


class GetDeviceView(SingleObjectMixin, View):
    """
    Base view that implements a ``get_object`` method
    Subclassed by all device views which deal with existing objects
    """

    model = Device

    def get_object(self, *args, **kwargs):
        kwargs.update({'organization__is_active': True, 'config__isnull': False})
        defer = (
            'notes',
            'organization__name',
            'organization__description',
            'organization__email',
            'organization__url',
            'organization__created',
            'organization__modified',
        )
        queryset = self.model.objects.select_related('organization', 'config').defer(
            *defer
        )
        return get_object_or_404(queryset, *args, **kwargs)


class CsrfExtemptMixin(object):
    """
    Mixin that makes the view extempt from CSFR protection
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class UpdateLastIpMixin(object):
    def update_last_ip(self, device, request):
        result = update_last_ip(device, request)
        if result:
            self._remove_duplicated_management_ip(device)
            self._remove_duplicated_last_ip(device)
        return result

    def _remove_duplicated_management_ip(self, device):
        # Ensures that two devices does not have same management_ip.
        # This can happen when management interfaces are using DHCP
        # and they get a new address which was previously used by another
        # device that may now be offline. Without this, two devices will
        # have the same management_ip which will confuse OpenWISP.
        if not device.management_ip:
            return
        where = Q(management_ip=device.management_ip)
        if not app_settings.SHARED_MANAGEMENT_IP_ADDRESS_SPACE:
            where &= Q(organization_id=device.organization_id)

        queryset = self.model.objects.filter(where).exclude(pk=device.pk)
        for dupe in queryset.only('pk', 'key', 'management_ip'):
            dupe.management_ip = ''
            dupe.save(update_fields=['management_ip'])

    def _remove_duplicated_last_ip(self, device):
        # in the case of last_ip, we take a different approach,
        # because it may be a public IP. If it's a public IP we will
        # allow it to be duplicated
        if not device.last_ip or not ip_address(device.last_ip).is_private:
            return
        where = Q(last_ip=device.last_ip)
        if not app_settings.SHARED_MANAGEMENT_IP_ADDRESS_SPACE:
            where &= Q(organization_id=device.organization_id)

        queryset = self.model.objects.filter(where).exclude(pk=device.pk)
        for dupe in queryset.only('pk', 'key', 'last_ip'):
            dupe.last_ip = ''
            dupe.save(update_fields=['last_ip'])


def get_device_args_rewrite(view):
    """
    Use only the PK parameter for calculating the cache key
    """
    # avoid ambiguity between hex format and dashed string
    # return view.kwargs['pk']
    pk = view.kwargs['pk']
    try:
        pk = uuid.UUID(pk)
    except ValueError:
        return pk
    return pk.hex


class DeviceChecksumView(UpdateLastIpMixin, GetDeviceView):
    """
    returns device's configuration checksum
    """

    def get(self, request, pk):
        device = self.get_device()
        bad_request = forbid_unallowed(request, 'GET', 'key', device.key)
        if bad_request:
            return bad_request
        updated = self.update_last_ip(device, request)
        # updates cache if ip addresses changed
        if updated:
            self.update_device_cache(device)
        checksum_requested.send(
            sender=device.__class__, instance=device, request=request
        )
        return ControllerResponse(
            device.config.get_cached_checksum(), content_type='text/plain'
        )

    @cache_memoize(
        timeout=Config._CHECKSUM_CACHE_TIMEOUT, args_rewrite=get_device_args_rewrite
    )
    def get_device(self):
        pk = self.kwargs['pk']
        logger.debug(f'retrieving device ID {pk} from DB')
        return self.get_object(pk=pk)

    def update_device_cache(self, device):
        cache.set(self.get_device.get_cache_key(self), device)

    @classmethod
    def invalidate_get_device_cache(cls, instance, **kwargs):
        """
        Called from signal receiver which performs cache invalidation
        """
        view = cls()
        pk = str(instance.pk.hex)
        view.kwargs = {'pk': pk}
        view.get_device.invalidate(view)
        logger.debug(f'invalidated view cache for device ID {pk}')

    @classmethod
    def invalidate_checksum_cache(cls, instance, device, **kwargs):
        """
        Called from signal receiver which performs cache invalidation
        """
        instance.get_cached_checksum.invalidate(instance)


class DeviceDownloadConfigView(GetDeviceView):
    """
    returns configuration archive as attachment
    """

    def get(self, request, *args, **kwargs):
        device = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'GET', 'key', device.key)
        if bad_request:
            return bad_request
        config_download_requested.send(
            sender=device.__class__, instance=device, request=request
        )
        return send_device_config(device.config, request)


class DeviceUpdateInfoView(CsrfExtemptMixin, GetDeviceView):
    """
    updates general information about the device
    """

    UPDATABLE_FIELDS = ['os', 'model', 'system']

    def post(self, request, *args, **kwargs):
        device = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'POST', 'key', device.key)
        if bad_request:
            return bad_request
        # update device information
        for attr in self.UPDATABLE_FIELDS:
            if attr in request.POST:
                # ignore empty values
                value = request.POST.get(attr).strip()
                if value:
                    setattr(device, attr, value)
        # validate and save everything or fail otherwise
        try:
            device.full_clean()
            device.save()
        except ValidationError as e:
            # dump message_dict as JSON,
            # this should make it easy to debug
            return ControllerResponse(
                json.dumps(e.message_dict, indent=4, sort_keys=True),
                content_type='text/plain',
                status=400,
            )
        return ControllerResponse('update-info: success', content_type='text/plain')


class DeviceReportStatusView(CsrfExtemptMixin, GetDeviceView):
    """
    updates status of config objects
    """

    def post(self, request, *args, **kwargs):
        device = self.get_object(*args, **kwargs)
        config = device.config
        # ensure request is well formed and authorized
        allowed_status = [choices[0] for choices in config.STATUS]
        allowed_status.append('running')  # backward compatibility
        required_params = [('key', device.key), ('status', allowed_status)]
        for key, value in required_params:
            bad_response = forbid_unallowed(request, 'POST', key, value)
            if bad_response:
                return bad_response
        status = request.POST.get('status')
        # mantain backward compatibility with old agents
        # ("running" was changed to "applied")
        status = status if status != 'running' else 'applied'
        # call set_status_{status} method on Config model
        method_name = f'set_status_{status}'
        getattr(config, method_name)()
        return ControllerResponse(
            f'report-result: success\ncurrent-status: {config.status}\n',
            content_type='text/plain',
        )


class DeviceRegisterView(UpdateLastIpMixin, CsrfExtemptMixin, View):
    """
    registers new Config objects
    """

    model = Device
    org_config_settings_model = OrganizationConfigSettings

    UPDATABLE_FIELDS = ['os', 'model', 'system']

    def init_object(self, **kwargs):
        """
        initializes Config object with incoming POST data
        """
        device_model = self.model
        config_model = device_model.get_config_model()
        options = {}
        for attr in kwargs.keys():
            # skip attributes that are not model fields
            try:
                device_model._meta.get_field(attr)
            except FieldDoesNotExist:
                continue
            options[attr] = kwargs.get(attr)
        # do not specify key if:
        #   app_settings.CONSISTENT_REGISTRATION is False
        #   if key is ``None`` (it would cause exception)
        if 'key' in options and (
            app_settings.CONSISTENT_REGISTRATION is False or options['key'] is None
        ):
            del options['key']
        if 'hardware_id' in options and options['hardware_id'] == "":
            options['hardware_id'] = None
        config = config_model(device=device_model(**options), backend=kwargs['backend'])
        config.organization = self.organization
        config.device.organization = self.organization
        return config

    def get_template_queryset(self, config):
        """
        returns Template model queryset
        """
        queryset = config.get_template_model().objects.all()
        # filter templates of the same organization or shared templates
        return queryset.filter(Q(organization=self.organization) | Q(organization=None))

    def add_tagged_templates(self, config, request):
        """
        adds templates specified in incoming POST tag setting
        """
        tags = request.POST.get('tags')
        if not tags:
            return
        # retrieve tags and add them to current config
        tags = tags.split()
        queryset = self.get_template_queryset(config)
        tagged_templates = queryset.filter(tags__name__in=tags).only('id').distinct()
        if tagged_templates:
            config.templates.add(*tagged_templates)

    def invalid(self, request):
        """
        ensures request is well formed
        """
        allowed_backends = [path for path, name in app_settings.BACKENDS]
        required_params = [
            ('secret', None),
            ('name', None),
            ('mac_address', None),
            ('backend', allowed_backends),
        ]
        # valid required params or forbid
        for key, value in required_params:
            invalid_response = forbid_unallowed(request, 'POST', key, value)
            if invalid_response:
                return invalid_response

    def forbidden(self, request):
        """
        ensures request is authorized:
            - secret matches an organization's shared_secret
            - the organization has registration_enabled set to True
        """
        try:
            secret = request.POST.get('secret')
            org_settings = self.org_config_settings_model.objects.select_related(
                'organization'
            ).get(shared_secret=secret, organization__is_active=True)
        except self.org_config_settings_model.DoesNotExist:
            return invalid_response(request, 'error: unrecognized secret', status=403)
        if not org_settings.registration_enabled:
            return invalid_response(request, 'error: registration disabled', status=403)
        # set an organization attribute as a side effect
        # this attribute will be used in ``init_object``
        self.organization = org_settings.organization

    def post(self, request, *args, **kwargs):
        """
        POST logic
        """
        if not app_settings.REGISTRATION_ENABLED:
            return ControllerResponse('error: registration disabled', status=403)
        # ensure request is valid
        bad_response = self.invalid(request)
        if bad_response:
            return bad_response
        # ensure request is allowed
        forbidden = self.forbidden(request)
        if forbidden:
            return forbidden
        # prepare model attributes
        key = None
        if app_settings.CONSISTENT_REGISTRATION:
            key = request.POST.get('key')
        # try retrieving existing Device first
        # (key is not None only if CONSISTENT_REGISTRATION is enabled)
        new = False
        try:
            device = self.model.objects.get(key=key)
            # update hw info
            for attr in self.UPDATABLE_FIELDS:
                if attr in request.POST:
                    setattr(device, attr, request.POST.get(attr))
            config = device.config
        # if get queryset fails, instantiate a new Device and Config
        except self.model.DoesNotExist:
            if not app_settings.REGISTRATION_SELF_CREATION:
                return ControllerResponse(
                    'Device not found in the system, please create it first.',
                    status=404,
                )
            new = True
            config = self.init_object(**request.POST.dict())
            device = config.device
        # if get queryset succedes but device has no related config
        # instantiate new Config but reuse existing device
        except self.model.config.RelatedObjectDoesNotExist:
            config = self.init_object(**request.POST.dict())
            config.device = device
        # update last_ip field of device
        device.last_ip = request.META.get('REMOTE_ADDR')
        # validate and save everything or fail otherwise
        try:
            with transaction.atomic():
                device.full_clean()
                device.save()
                config.full_clean()
                config.save()
        except ValidationError as e:
            # dump message_dict as JSON,
            # this should make it easy to debug
            return ControllerResponse(
                json.dumps(e.message_dict, indent=4, sort_keys=True),
                content_type='text/plain',
                status=400,
            )
        # add templates specified in tags
        self.add_tagged_templates(config, request)
        # emit device registered signal
        device_registered.send(sender=device.__class__, instance=device, is_new=new)
        # prepare response
        s = (
            'registration-result: success\n'
            'uuid: {id}\n'
            'key: {key}\n'
            'hostname: {name}\n'
            'is-new: {is_new}\n'
        )
        attributes = device.__dict__.copy()
        attributes.update({'id': device.pk.hex, 'key': device.key, 'is_new': int(new)})
        return ControllerResponse(
            s.format(**attributes), content_type='text/plain', status=201
        )


class GetVpnView(SingleObjectMixin, View):
    """
    Base view that implements a ``get_object`` method
    Subclassed by all vpn views which deal with existing objects
    """

    model = Vpn

    def get_object(self, *args, **kwargs):
        queryset = self.model.objects.select_related('organization').filter(
            Q(organization__is_active=True) | Q(organization__isnull=True)
        )
        return get_object_or_404(queryset, *args, **kwargs)


class VpnChecksumView(GetVpnView):
    """
    returns vpn's configuration checksum
    """

    def get(self, request, *args, **kwargs):
        vpn = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'GET', 'key', vpn.key)
        if bad_request:
            return bad_request
        checksum_requested.send(sender=vpn.__class__, instance=vpn, request=request)
        return ControllerResponse(vpn.checksum, content_type='text/plain')


class VpnDownloadConfigView(GetVpnView):
    """
    returns configuration archive as attachment
    """

    def get(self, request, *args, **kwargs):
        vpn = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'GET', 'key', vpn.key)
        if bad_request:
            return bad_request
        config_download_requested.send(
            sender=vpn.__class__, instance=vpn, request=request
        )
        return send_vpn_config(vpn, request)


device_checksum = DeviceChecksumView.as_view()
device_download_config = DeviceDownloadConfigView.as_view()
device_update_info = DeviceUpdateInfoView.as_view()
device_report_status = DeviceReportStatusView.as_view()
device_register = DeviceRegisterView.as_view()
vpn_checksum = VpnChecksumView.as_view()
vpn_download_config = VpnDownloadConfigView.as_view()
