from django.core.exceptions import ImproperlyConfigured
from django.db import models

try:
    from rest_framework import serializers
except ImportError:  # pragma: nocover
    raise ImproperlyConfigured(
        "Django REST Framework is required to use "
        "this feature but it is not installed"
    )


class ValidatedModelSerializer(serializers.ModelSerializer):
    exclude_validation = None

    def validate(self, data):
        """Performs model validation on serialized data.

        Allows to avoid having to duplicate model validation logic in the
        REST API.
        """
        instance = self.instance
        # if instance is empty (eg: creation)
        # simulate for validation purposes
        if not instance:
            Model = self.Meta.model
            instance = Model()
            for key, value in data.items():
                # avoid direct assignment for m2m (not allowed)
                if not isinstance(Model._meta.get_field(key), models.ManyToManyField):
                    setattr(instance, key, value)
        # perform model validation
        instance.full_clean(exclude=self.exclude_validation)
        return data
