"""
Customized sortedm2m field that sends the pre_add and post_add
signals also when all the m2m relations are removed.
"""

from django.db import router
from django.db.models import signals
from django.utils.functional import cached_property
from sortedm2m.fields import (
    SortedManyToManyDescriptor as BaseSortedManyToManyDescriptor,
)
from sortedm2m.fields import SortedManyToManyField as BaseSortedManyToManyField
from sortedm2m.fields import (
    create_sorted_many_related_manager as base_create_sorted_many_related_manager,
)


def create_sorted_many_related_manager(superclass, rel, *args, **kwargs):
    BaseSortedRelatedManager = base_create_sorted_many_related_manager(
        superclass, rel, *args, **kwargs
    )

    class SortedRelatedManager(BaseSortedRelatedManager):
        def _add_items(self, source_field_name, target_field_name, *objs, **kwargs):
            db = router.db_for_write(self.through, instance=self.instance)
            super()._add_items(source_field_name, target_field_name, *objs, **kwargs)
            if not objs and (
                self.reverse or source_field_name == self.source_field_name
            ):
                signals.m2m_changed.send(
                    sender=self.through,
                    action='pre_add',
                    instance=self.instance,
                    reverse=self.reverse,
                    model=self.model,
                    pk_set=set(),
                    using=db,
                )
                signals.m2m_changed.send(
                    sender=self.through,
                    action='post_add',
                    instance=self.instance,
                    reverse=self.reverse,
                    model=self.model,
                    pk_set=set(),
                    using=db,
                )

    return SortedRelatedManager


class SortedManyToManyDescriptor(BaseSortedManyToManyDescriptor):
    @cached_property
    def related_manager_cls(self):
        model = self.rel.model
        return create_sorted_many_related_manager(
            model._default_manager.__class__,
            self.rel,
            reverse=False,
        )


class SortedManyToManyField(BaseSortedManyToManyField):
    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        setattr(cls, self.name, SortedManyToManyDescriptor(self))
