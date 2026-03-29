from django.contrib import admin
from django.shortcuts import render
from django.urls import path

from django_loci.admin import ObjectLocationInline
from openwisp_utils.admin import TimeReadonlyAdminMixin

from .models import Device


class DeviceAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "created", "modified")
    save_on_top = True
    inlines = [ObjectLocationInline]

    def get_urls(self):
        urls = super().get_urls()
        urls = [
            path(
                "location-broadcast-listener/",
                self.admin_site.admin_view(self.location_broadcast_listener),
                name="location-broadcast-listener",
            ),
        ] + urls
        return urls

    def location_broadcast_listener(self, request):
        return render(
            request,
            "admin/location_broadcast_listener.html",
            {"title": "Location Broadcast Listener", "site_title": "OpenWISP 2"},
        )


admin.site.register(Device, DeviceAdmin)
