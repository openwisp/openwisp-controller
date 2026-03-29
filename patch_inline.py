import re
with open('openwisp_controller/config/admin.py', 'r') as f:
    content = f.read()

old_str = """class ConfigSettingsInline(admin.StackedInline):
    model = OrganizationConfigSettings
    form = ConfigSettingsForm

    def get_fields(self, request, obj=None):
        fields = []
        if app_settings.REGISTRATION_ENABLED:
            fields += ["registration_enabled", "shared_secret"]
        if app_settings.WHOIS_CONFIGURED:
            fields += ["whois_enabled", "estimated_location_enabled"]
        fields += ["context"]
        return fields"""

new_str = """class ConfigSettingsInline(ReadonlyPrettyJsonMixin, admin.StackedInline):
    model = OrganizationConfigSettings
    form = ConfigSettingsForm
    readonly_json_fields = {"context": "pretty_context"}

    fields = []
    if app_settings.REGISTRATION_ENABLED:
        fields += ["registration_enabled", "shared_secret"]
    if app_settings.WHOIS_CONFIGURED:
        fields += ["whois_enabled", "estimated_location_enabled"]
    fields += ["context"]

    def pretty_context(self, obj):
        return self._format_json_field(obj, "context")

    pretty_context.short_description = _("Configuration Variables")"""

if old_str in content:
    with open('openwisp_controller/config/admin.py', 'w') as f:
        f.write(content.replace(old_str, new_str))
    print('Replaced successfully.')
else:
    print('Could not find exact string.')
