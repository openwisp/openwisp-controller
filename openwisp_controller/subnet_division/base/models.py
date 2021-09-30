from ipaddress import ip_network

import swapper
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

from openwisp_users.mixins import OrgMixin
from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings


class AbstractSubnetDivisionRule(TimeStampedEditableModel, OrgMixin):
    _subnet_division_rule_update_queue = dict()
    # It is used to monitor changes in fields of a SubnetDivisionRule object
    # An entry is added to the queue from pre_save signal in the following format
    #
    # '<rule-uid>: {
    #   '<field-name>': '<old-value>',
    # }
    #
    # In post_save signal, it is checked whether entry for SubnetDivisionRule object
    # exists in this queue. If it exists changes are made to related objects.

    type = models.CharField(max_length=200, choices=app_settings.SUBNET_DIVISION_TYPES)
    master_subnet = models.ForeignKey(
        swapper.get_model_name('openwisp_ipam', 'Subnet'), on_delete=models.CASCADE
    )
    label = models.CharField(
        max_length=30,
        help_text=_('Label used to calculate the configuration variables'),
    )
    number_of_subnets = models.PositiveIntegerField(
        verbose_name=_('Number of Subnets'),
        help_text=_('Indicates how many subnets will be created'),
    )
    size = models.PositiveIntegerField(
        verbose_name=_('Size of subnets'),
        help_text=_('Indicates the size of each created subnet'),
    )
    number_of_ips = models.PositiveIntegerField(
        verbose_name=_('Number of IPs'),
        help_text=_('Indicates how many IP addresses will be created for each subnet'),
    )

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'label'],
                name='unique_subnet_division_rule_label',
            ),
            models.UniqueConstraint(
                fields=['organization', 'label', 'type', 'master_subnet'],
                name='unique_subnet_division_rule',
            ),
        ]

    def __str__(self):
        return f'{self.label}'

    @property
    def rule_class(self):
        return import_string(self.type)

    def clean(self):
        super().clean()
        self._validate_label()
        self._validate_master_subnet_consistency()
        self._validate_ip_address_consistency()
        if not self._state.adding:
            self._validate_existing_fields()

    def _validate_label(self):
        if not self.label.isidentifier():
            raise ValidationError(
                {
                    'label': _(
                        'Only alphanumeric characters and underscores are allowed.'
                    )
                }
            )

    def _validate_existing_fields(self):
        db_instance = self._meta.model.objects.get(id=self.id)
        # The size field should not be changed
        if self.size != db_instance.size:
            raise ValidationError({'size': _('Subnet size cannot be changed')})
        # Number of IPs should not decreased
        if self.number_of_ips < db_instance.number_of_ips:
            raise ValidationError(
                {'number_of_ips': _('Number of IPs cannot be decreased')}
            )
        # Number of subnets should not be changed
        if self.number_of_subnets != db_instance.number_of_subnets:
            raise ValidationError(
                {'number_of_subnets': _('Number of Subnets cannot be changed')}
            )

    def _validate_master_subnet_consistency(self):
        master_subnet = self.master_subnet.subnet
        # Validate size of generated subnet is not greater than size of master subnet
        try:
            next(master_subnet.subnets(new_prefix=self.size))
        except ValueError:
            raise ValidationError(
                {
                    'size': _(
                        'Master subnet cannot accommodate subnets of size /{0}'.format(
                            self.size
                        )
                    )
                }
            )

        # Validate master subnet can accommodate required number of generated subnets
        if self.number_of_subnets > (2 ** (self.size - master_subnet.prefixlen)):
            raise ValidationError(
                {
                    'number_of_subnets': _(
                        f'Master subnet cannot accommodate {self.number_of_subnets} '
                        f'subnets of size /{self.size}'
                    )
                }
            )

        # Validate organization of master subnet
        if (
            self.master_subnet.organization is not None
            and self.master_subnet.organization != self.organization
        ):
            raise ValidationError(
                {'organization': _('Organization should be same as the subnet')}
            )

    def _validate_ip_address_consistency(self):
        # Validate individual generated subnet can accommodate required number of IPs
        try:
            next(
                ip_network(str(self.master_subnet.subnet)).subnets(new_prefix=self.size)
            )[self.number_of_ips]
        except IndexError:
            raise ValidationError(
                {
                    'number_of_ips': _(
                        f'Generated subnets of size /{self.size} cannot accommodate '
                        f'{self.number_of_ips} IP Addresses.'
                    )
                }
            )

    def check_and_queue_modified_fields(self):
        try:
            db_instance = self._meta.model.objects.get(id=self.id)
        except self._meta.model.DoesNotExist:
            # This rule does not exists in database.
            # No operation is needed to be performed.
            return
        else:
            # Check which fields of instance is modified
            # NOTE: Open-ended implementation to allow change in all
            # fields of SubnetDivisionRule in future.
            # Currently only changing label and number of IPs is allowed.
            modified_fields = {}
            for field in db_instance._meta.fields:
                instance_value = getattr(self, field.name)
                db_value = getattr(db_instance, field.name)
                if instance_value != db_value:
                    modified_fields[field.name] = db_value
            if modified_fields:
                self._subnet_division_rule_update_queue[str(self.id)] = modified_fields

    def update_related_objects(self):
        from .. import tasks

        # Update related objects appropriately.
        # NOTE: Currently only changing label and number of IPs is implemented/allowed.
        try:
            modified_fields = self._subnet_division_rule_update_queue.pop(str(self.id))
        except KeyError:
            return
        else:
            if 'label' in modified_fields:
                tasks.update_subnet_division_index.delay(rule_id=str(self.id))
                tasks.update_subnet_name_description(rule_id=str(self.id))
            if 'number_of_ips' in modified_fields:
                tasks.provision_extra_ips.delay(
                    rule_id=str(self.id),
                    old_number_of_ips=modified_fields['number_of_ips'],
                )

    def delete_provisioned_subnets(self):
        # Deleting an object of SubnetDivisionRule will set the rule field
        # of related SubnetDivisionIndex to "None" due to "on_delete=SET_NULL".
        # These indexes are used delete subnets that were provisioned by the
        # deleted rule. Deleting a Subnet object will automatically delete
        # related IpAddress objects.
        Subnet = swapper.load_model('openwisp_ipam', 'Subnet')
        SubnetDivisionIndex = swapper.load_model(
            'subnet_division', 'SubnetDivisionIndex'
        )

        Subnet.objects.filter(
            id__in=SubnetDivisionIndex.objects.filter(rule_id=None).values('subnet_id')
        ).delete()

    @classmethod
    def pre_save(cls, instance, **kwargs):
        instance.check_and_queue_modified_fields()

    @classmethod
    def post_save(cls, instance, created, **kwargs):
        from ..tasks import provision_subnet_ip_for_existing_devices

        if created:
            transaction.on_commit(
                lambda: provision_subnet_ip_for_existing_devices.delay(
                    rule_id=instance.id
                )
            )
        else:
            transaction.on_commit(instance.update_related_objects)

    @classmethod
    def post_delete(cls, instance, **kwargs):
        transaction.on_commit(instance.delete_provisioned_subnets)


class AbstractSubnetDivisionIndex(models.Model):
    keyword = models.CharField(max_length=30)
    subnet = models.ForeignKey(
        swapper.get_model_name('openwisp_ipam', 'Subnet'),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    ip = models.ForeignKey(
        swapper.get_model_name('openwisp_ipam', 'IpAddress'),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    rule = models.ForeignKey(
        swapper.get_model_name('subnet_division', 'SubnetDivisionRule'),
        null=True,
        on_delete=models.SET_NULL,
    )
    config = models.ForeignKey(
        swapper.get_model_name('config', 'Config'),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['keyword']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['keyword', 'subnet', 'ip', 'config'],
                name='unique_subnet_division_index',
            ),
        ]
