from django.db import models

from openwisp_controller.subnet_division.base.models import (
    AbstractSubnetDivisionIndex,
    AbstractSubnetDivisionRule,
)


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class SubnetDivisionRule(DetailsModel, AbstractSubnetDivisionRule):
    class Meta(AbstractSubnetDivisionRule.Meta):
        abstract = False


class SubnetDivisionIndex(DetailsModel, AbstractSubnetDivisionIndex):
    class Meta(AbstractSubnetDivisionIndex.Meta):
        abstract = False
