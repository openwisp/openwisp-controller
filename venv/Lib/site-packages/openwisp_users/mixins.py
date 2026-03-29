"""
mixins used by other openwisp components to implement multi-tenancy
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name


class ValidateOrgMixin(object):
    """
    - implements ``_validate_org_relation`` method
    """

    def _validate_org_relation(self, rel, field_error="organization"):
        """
        if the relation is owned by a specific organization
        this object must be related to the same organization
        """
        # avoid exceptions caused by the relation not being set
        if not hasattr(self, rel):
            return
        rel = getattr(self, rel)
        if (
            rel
            and rel.organization_id
            and str(self.organization_id) != str(rel.organization_id)
        ):
            message = _(
                "Please ensure that the organization of this {object_label} "
                "and the organization of the related {related_object_label} match."
            )
            message = message.format(
                object_label=self._meta.verbose_name,
                related_object_label=rel._meta.verbose_name,
            )
            raise ValidationError({field_error: message})

    def _validate_org_reverse_relation(self, rel_name, field_error="organization"):
        """
        prevents changing organization for existing objects
        which have relations specified by ``rel_name`` pointing to them,
        in order to prevent inconsistencies
        (relations belonging to different organizations)
        """
        # do nothing on new objects, because they
        # cannot have relations pointing to them
        if self._state.adding:
            return
        old_self = self.__class__.objects.get(pk=self.pk)
        old_org = old_self.organization
        # org hasn't been changed, everything ok
        if old_org == self.organization:
            return
        rel = getattr(self, rel_name)
        count = rel.count()
        if count:
            rel_meta = rel.model._meta
            related_label = (
                rel_meta.verbose_name if count == 1 else rel_meta.verbose_name_plural
            )
            verb = _("is") if count == 1 else _("are")
            message = _(
                "The organization of this {object_label} cannot be changed "
                "because {0} {related_object_label} {verb} still "
                "related to it".format(
                    count,
                    object_label=self._meta.verbose_name,
                    related_object_label=related_label,
                    verb=verb,
                )
            )
            raise ValidationError({field_error: message})


class OrgMixin(ValidateOrgMixin, models.Model):
    """
    - adds a ``ForeignKey`` field to the ``Organization`` model
      (the relation cannot be NULL)
    - implements ``_validate_org_relation`` method
    """

    organization = models.ForeignKey(
        get_model_name("openwisp_users", "Organization"),
        verbose_name=_("organization"),
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True


class ShareableOrgMixin(OrgMixin):
    """
    like ``OrgMixin``, but the relation can be NULL, in which
    case it means that the object can be shared between multiple organizations
    """

    class Meta:
        abstract = True


_org_field = ShareableOrgMixin._meta.get_field("organization")
_org_field.blank = True
_org_field.null = True
