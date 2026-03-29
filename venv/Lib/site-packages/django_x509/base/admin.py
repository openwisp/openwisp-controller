from django import forms
from django.contrib import messages
from django.contrib.admin import ModelAdmin, action
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from django_x509 import settings as app_settings


class X509Form(forms.ModelForm):
    OPERATION_CHOICES = (
        ("-", "----- {0} -----".format(_("Please select an option"))),
        ("new", _("Create new")),
        ("import", _("Import Existing")),
    )
    operation_type = forms.ChoiceField(choices=OPERATION_CHOICES)


class BaseAdmin(ModelAdmin):
    """
    ModelAdmin for TimeStampedEditableModel
    """

    list_display = [
        "name",
        "key_length",
        "digest",
        "validity_end",
        "created",
        "modified",
    ]
    search_fields = ["name", "serial_number", "common_name"]
    actions_on_bottom = True
    save_on_top = True
    form = X509Form
    # custom attribute
    readonly_edit = [
        "key_length",
        "digest",
        "validity_start",
        "validity_end",
        "country_code",
        "state",
        "city",
        "organization_name",
        "organizational_unit_name",
        "email",
        "common_name",
        "serial_number",
        "certificate",
        "private_key",
    ]

    class Media:
        css = {"all": ("django-x509/css/admin.css",)}

    def __init__(self, *args, **kwargs):
        self.readonly_fields += ("created", "modified")
        super().__init__(*args, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        # edit
        if obj:
            return tuple(self.readonly_edit) + tuple(self.readonly_fields)
        # add
        else:
            return self.readonly_fields

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        # edit
        if obj:
            fields = fields[:]  # make copy
            fields.remove("extensions")
            fields.remove("passphrase")
        return fields

    def get_context(self, data, ca_count=0, cert_count=0):
        context = dict()
        if ca_count:
            context.update(
                {
                    "title": _("Renew selected CAs"),
                    "ca_count": ca_count,
                    "cert_count": cert_count,
                    "cancel_url": f"{self.opts.app_label}_ca_changelist",
                    "action": "renew_ca",
                }
            )
        else:
            context.update(
                {
                    "title": _("Renew selected certs"),
                    "cert_count": cert_count,
                    "cancel_url": f"{self.opts.app_label}_cert_changelist",
                    "action": "renew_cert",
                }
            )
        context.update({"opts": self.model._meta, "data": data})
        return context


class AbstractCaAdmin(BaseAdmin):
    list_filter = ["key_length", "digest", "created"]
    fields = [
        "operation_type",
        "name",
        "notes",
        "key_length",
        "digest",
        "validity_start",
        "validity_end",
        "country_code",
        "state",
        "city",
        "organization_name",
        "organizational_unit_name",
        "email",
        "common_name",
        "extensions",
        "serial_number",
        "certificate",
        "private_key",
        "passphrase",
        "created",
        "modified",
    ]
    actions = ["renew_ca"]

    class Media:
        js = ("admin/js/jquery.init.js", "django-x509/js/x509-admin.js")

    def get_urls(self):
        return [
            path("<int:pk>.crl", self.crl_view, name="crl"),
            # old URL path, deprecated, will be removed in future versions
            path("x509/ca/<int:pk>.crl", self.crl_view, name="deprecated_crl"),
        ] + super().get_urls()

    def crl_view(self, request, pk):
        authenticated = request.user.is_authenticated
        authenticated = authenticated() if callable(authenticated) else authenticated
        if app_settings.CRL_PROTECTED and not authenticated:
            return HttpResponse(_("Forbidden"), status=403, content_type="text/plain")
        instance = get_object_or_404(self.model, pk=pk)
        return HttpResponse(
            instance.crl, status=200, content_type="application/x-pem-file"
        )

    @action(description=_("Renew selected CAs"), permissions=["change"])
    def renew_ca(self, request, queryset):
        if request.POST.get("post"):
            renewed_rows = 0
            for ca in queryset:
                ca.renew()
                renewed_rows += 1
            message = ngettext(
                (
                    "%(renewed_rows)d CA and its related certificates have "
                    "been successfully renewed"
                ),
                (
                    "%(renewed_rows)d CAs and their related "
                    "certificates have been successfully renewed"
                ),
                renewed_rows,
            ) % {"renewed_rows": renewed_rows}
            self.message_user(request, message, level=messages.SUCCESS)
        else:
            data = dict()
            ca_count = 0
            cert_count = 0
            for ca in queryset:
                ca_count += 1
                certs = ca.cert_set.all()
                cert_count += len(certs)
                data[ca] = certs
            return render(
                request,
                "admin/django_x509/renew_confirmation.html",
                context=self.get_context(
                    data, ca_count=ca_count, cert_count=cert_count
                ),
            )


class AbstractCertAdmin(BaseAdmin):
    list_filter = ["ca", "revoked", "key_length", "digest", "created"]
    list_select_related = ["ca"]
    readonly_fields = ["revoked", "revoked_at"]
    fields = [
        "operation_type",
        "name",
        "ca",
        "notes",
        "revoked",
        "revoked_at",
        "key_length",
        "digest",
        "validity_start",
        "validity_end",
        "country_code",
        "state",
        "city",
        "organization_name",
        "organizational_unit_name",
        "email",
        "common_name",
        "extensions",
        "serial_number",
        "certificate",
        "private_key",
        "passphrase",
        "created",
        "modified",
    ]
    actions = ["revoke_action", "renew_cert"]
    autocomplete_fields = ["ca"]

    class Media:
        js = ("admin/js/jquery.init.js", "django-x509/js/x509-admin.js")

    def ca_url(self, obj):
        url = reverse(
            "admin:{0}_ca_change".format(self.opts.app_label), args=[obj.ca.pk]
        )
        return format_html('<a href="{url}">{text}</a>', url=url, text=obj.ca.name)

    ca_url.short_description = "CA"

    @action(description=_("Revoke selected certificates"), permissions=["change"])
    def revoke_action(self, request, queryset):
        rows = 0
        for cert in queryset:
            cert.revoke()
            rows += 1
        if rows == 1:
            bit = "1 certificate was"
        else:
            bit = "{0} certificates were".format(rows)
        message = "{0} revoked.".format(bit)
        self.message_user(request, _(message), level=messages.SUCCESS)

    @action(description=_("Renew selected certificates"), permissions=["change"])
    def renew_cert(self, request, queryset):
        if request.POST.get("post"):
            renewed_rows = 0
            for cert in queryset:
                cert.renew()
                renewed_rows += 1
            message = ngettext(
                "%(renewed_rows)d Certificate has been successfully renewed",
                "%(renewed_rows)d Certificates have been successfully renewed",
                renewed_rows,
            ) % {"renewed_rows": renewed_rows}
            self.message_user(request, message, level=messages.SUCCESS)
        else:
            return render(
                request,
                "admin/django_x509/renew_confirmation.html",
                context=self.get_context(queryset, cert_count=len(queryset)),
            )


# For backward compatibility
CaAdmin = AbstractCaAdmin
CertAdmin = AbstractCertAdmin

AbstractCertAdmin.list_display = BaseAdmin.list_display[:]
AbstractCertAdmin.list_display.insert(1, "ca_url")
AbstractCertAdmin.list_display.insert(5, "revoked")
AbstractCertAdmin.readonly_edit = BaseAdmin.readonly_edit[:]
AbstractCertAdmin.readonly_edit += ("ca",)
