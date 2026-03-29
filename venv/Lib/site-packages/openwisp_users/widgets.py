from django.contrib.admin.widgets import AutocompleteSelect as BaseAutocompleteSelect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

SHARED_SYSTEMWIDE_LABEL = _("Shared systemwide (no organization)")


class OrganizationAutocompleteSelect(BaseAutocompleteSelect):
    class Media:
        js = ["admin/js/jquery.init.js", "openwisp-users/js/org-autocomplete.js"]

    def get_url(self):
        return reverse("admin:ow-auto-filter")

    def optgroups(self, name, value, attrs=None):
        groups = super().optgroups(name, value, attrs)
        if value == [""] and len(groups[0][1]) == 1:
            groups[0][1].append(
                self.create_option(
                    name=name,
                    value="null",
                    label=SHARED_SYSTEMWIDE_LABEL,
                    selected=False,
                    index=2,
                    attrs=attrs,
                )
            )
        return groups
