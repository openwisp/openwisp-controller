from django.core.exceptions import ValidationError


class UnqiueCommonNameMixin(object):
    def validate_unique(self, exclude=None):
        super().validate_unique(exclude=exclude)
        if (
            self.organization is None
            and self._meta.model.objects.filter(
                organization=None, common_name=self.common_name
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                {
                    '__all__': [
                        f'{self._meta.model._meta.verbose_name} with this Common name '
                        'and Organization already exists.'
                    ]
                }
            )
