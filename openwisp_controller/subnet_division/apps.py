from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save, pre_save
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from . import settings as app_settings
from .utils import get_subnet_division_config_context, subnet_division_vpnclient_auto_ip


class SubnetDivisionConfig(AppConfig):
    name = 'openwisp_controller.subnet_division'
    verbose_name = _('Subnet Division')
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        super().ready()
        self._load_models()
        self._add_config_context_method()

        for rule_path, name in app_settings.SUBNET_DIVISION_TYPES:
            rule_class = import_string(rule_path)
            rule_class.validate_rule_type()
            rule_class.provision_signal.connect(
                receiver=rule_class.provision_receiver,
                sender=rule_class.provision_sender,
                dispatch_uid=rule_class.provision_dispatch_uid,
            )
            rule_class.destroyer_signal.connect(
                receiver=rule_class.destroyer_receiver,
                sender=rule_class.destroyer_sender,
                dispatch_uid=rule_class.destroyer_dispatch_uid,
            )

        pre_save.connect(
            receiver=self.subnetdivisionrule_model_.pre_save,
            sender=self.subnetdivisionrule_model_,
            dispatch_uid='subnetdivisionrule_pre_save',
        )
        post_save.connect(
            receiver=self.subnetdivisionrule_model_.post_save,
            sender=self.subnetdivisionrule_model_,
            dispatch_uid='subnetdivisionrule_post_save',
        )
        post_delete.connect(
            receiver=self.subnetdivisionrule_model_.post_delete,
            sender=self.subnetdivisionrule_model_,
            dispatch_uid='subnetdivisionrule_post_delete',
        )

    def _load_models(self):
        self.subnetdivisionrule_model_ = load_model(
            'subnet_division', 'SubnetDivisionRule'
        )

    def _add_config_context_method(self):
        from openwisp_controller.config.tests import CreateConfigTemplateMixin

        from .tests.helpers import subnetdivision_patched_assertNumQueries

        Config = load_model('config', 'Config')
        VpnClient = load_model('config', 'VpnClient')

        Config.register_context_function(get_subnet_division_config_context)
        VpnClient.register_auto_ip_stopper(subnet_division_vpnclient_auto_ip)

        # Monkeypatching of "CreateConfigTemplateMixin" is required because
        # subnet_division app updates context of the Config object
        # which creates additional database queries.
        # Usage of subnet_division app is optional hence, tests in
        # "openwisp_controller.config" are written assuming
        # subnet_division is not used. But when it is used, the number
        # of queries should be increased.
        CreateConfigTemplateMixin.assertNumQueries = (
            subnetdivision_patched_assertNumQueries
        )
