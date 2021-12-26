from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from openwisp_users.mixins import ShareableOrgMixin


class ShareableOrgMixinUniqueName(ShareableOrgMixin):
    """
    Like ShareableOrgMixin but performs special validation on the name
    """

    # needed to turn on the special validation in preview
    _validate_name = True

    class Meta:
        abstract = True

    def clean(self, *args, **kwargs):
        if self._validate_name:
            self._clean_name()
        return super().clean(*args, **kwargs)

    def _clean_name(self):
        model = self.__class__
        model_name = model.__name__.lower()
        qs = model.objects.filter(name=self.name)
        if not self._state.adding:
            qs = qs.exclude(id=self.id)
        shared_message = _(
            'Shared objects are visible to all organizations and '
            'must have unique names to avoid confusion.'
        )

        if qs.filter(organization=None).exists():
            msg = _(f'There is already another shared {model_name} with this name.')
            raise ValidationError({'name': f'{msg} {shared_message}'})

        if not self.organization and qs.filter(organization__isnull=False).exists():
            msg = _(
                f'There is already a {model_name} of '
                'another organization with this name.'
            )
            raise ValidationError({'name': f'{msg} {shared_message}'})
