import swapper
from asgiref.sync import async_to_sync
from django_loci.channels.base import BaseCommonLocationBroadcast, BaseLocationBroadcast

Location = swapper.load_model("geo", "Location")


class LocationBroadcast(BaseLocationBroadcast):
    model = Location

    def is_authorized(self, user, location):
        result = super().is_authorized(user, location)
        # non superusers must also be members of the org
        if (
            result
            and not user.is_superuser
            and not user.is_manager(location.organization)
        ):
            return False
        return result


class CommonLocationBroadcast(BaseCommonLocationBroadcast):
    model = Location

    def join_groups(self, user):
        """
        Subscribe user to all organizations they manage or bypass if superuser.
        """
        if user.is_superuser:
            super().join_groups(user)
            self.group_name = [self.group_name]
            return
        self.group_name = []
        for org in user.organizations_managed:
            group = f"loci.mobile-location.organization.{org}"
            self.group_name.append(group)
            async_to_sync(self.channel_layer.group_add)(group, self.channel_name)

    def disconnect(self, close_code):
        for group in getattr(self, "group_name", []):
            async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)
