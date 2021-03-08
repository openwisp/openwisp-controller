from swapper import swappable_setting

from .base.models import AbstractSubnetDivisionIndex, AbstractSubnetDivisionRule


class SubnetDivisionRule(AbstractSubnetDivisionRule):
    class Meta(AbstractSubnetDivisionRule.Meta):
        abstract = False
        swappable = swappable_setting('subnet_division', 'SubnetDivisionRule')


class SubnetDivisionIndex(AbstractSubnetDivisionIndex):
    class Meta(AbstractSubnetDivisionIndex.Meta):
        abstract = False
        swappable = swappable_setting('subnet_division', 'SubnetDivisionIndex')
