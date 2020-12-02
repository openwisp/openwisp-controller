import json
from ipaddress import ip_address

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
OrganizationConfigSettings = load_model('config', 'OrganizationConfigSettings')
Vpn = load_model('config', 'Vpn')


class BaseConfigView(SingleObjectMixin, View):
    """
    Base view that implements a ``get_object`` method
    Subclassed by all views dealing with existing objects
    """

    def get_object(self, *args, **kwargs):
        kwargs['config__isnull'] = False
        return get_object_or_404(self.model, *args, **kwargs)


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
            # avoid that any other device in the
            # same org stays with the same management_ip
            # This can happen when management interfaces are using DHCP
            # and they get a new address which was previously used by another
            # device that may now be offline, without this fix, we will end up
            # with two devices having the same management_ip, which will
            # cause OpenWISP to be confused
            self.model.objects.filter(
                organization=device.organization, management_ip=device.management_ip,
            ).exclude(pk=device.pk).update(management_ip='')
            # in the case of last_ip, we take a different approach,
            # because it may be a public IP. If it's a public IP we will
            # allow it to be duplicated
            if ip_address(device.last_ip).is_private:
                Device.objects.filter(
                    organization=device.organization, last_ip=device.last_ip,
                ).exclude(pk=device.pk).update(last_ip='')
        return result


class ActiveOrgMixin(object):
    """
    adds check to organization.is_active to ``get_object`` method
    """

    def get_object(self, *args, **kwargs):
        kwargs['organization__is_active'] = True
        return super().get_object(*args, **kwargs)


class DeviceChecksumView(ActiveOrgMixin, UpdateLastIpMixin, BaseConfigView):
    """
    returns device's configuration checksum
    """

    model = Device

    def get(self, request, *args, **kwargs):
        device = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'GET', 'key', device.key)
        if bad_request:
            return bad_request
        self.update_last_ip(device, request)
        checksum_requested.send(
            sender=device.__class__, instance=device, request=request
        )
        return ControllerResponse(device.config.checksum, content_type='text/plain')


class DeviceDownloadConfigView(ActiveOrgMixin, BaseConfigView):
    """
    returns configuration archive as attachment
    """

    model = Device

    def get(self, request, *args, **kwargs):
        device = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'GET', 'key', device.key)
        if bad_request:
            return bad_request
        config_download_requested.send(
            sender=device.__class__, instance=device, request=request
        )
        return send_device_config(device.config, request)


class DeviceUpdateInfoView(ActiveOrgMixin, CsrfExtemptMixin, BaseConfigView):
    """
    updates general information about the device
    """

    model = Device

    UPDATABLE_FIELDS = ['os', 'model', 'system']

    def post(self, request, *args, **kwargs):
        device = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'POST', 'key', device.key)
        if bad_request:
            return bad_request
        # update device information
        for attr in self.UPDATABLE_FIELDS:
            if attr in request.POST:
                setattr(device, attr, request.POST.get(attr))
        # validate and save everything or fail otherwise
        try:
            with transaction.atomic():
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


class DeviceReportStatusView(ActiveOrgMixin, CsrfExtemptMixin, BaseConfigView):
    """
    updates status of config objects
    """

    model = Device

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
        templates = queryset.filter(tags__name__in=tags).only('id').distinct()
        for template in templates:
            config.templates.add(template)

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


class VpnChecksumView(BaseConfigView):
    """
    returns vpn's configuration checksum
    """

    model = Vpn

    def get(self, request, *args, **kwargs):
        vpn = self.get_object(*args, **kwargs)
        bad_request = forbid_unallowed(request, 'GET', 'key', vpn.key)
        if bad_request:
            return bad_request
        checksum_requested.send(sender=vpn.__class__, instance=vpn, request=request)
        return ControllerResponse(vpn.checksum, content_type='text/plain')


class VpnDownloadConfigView(BaseConfigView):
    """
    returns configuration archive as attachment
    """

    model = Vpn

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
