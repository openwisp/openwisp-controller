import swapper
from django_loci.channels.base import BaseLocationBroadcast

Location = swapper.load_model('geo', 'Location')


class LocationBroadcast(BaseLocationBroadcast):
    model = Location

    def is_authorized(self, user, location):
        result = super().is_authorized(user, location)
        # non superusers must also be members of the org
        if (
            result
            and not user.is_superuser
            and ((location.organization.pk,) not in user.organizations_pk)
        ):
            return False
        return result
