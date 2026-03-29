from openwisp_notifications.swapper import load_model
from openwisp_users.api.filters import OrganizationMembershipFilter

NotificationSetting = load_model("NotificationSetting")


class NotificationSettingFilter(OrganizationMembershipFilter):
    class Meta(OrganizationMembershipFilter.Meta):
        model = NotificationSetting
        fields = OrganizationMembershipFilter.Meta.fields + ["type"]
