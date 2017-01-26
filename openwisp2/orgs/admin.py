from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.utils.translation import ugettext_lazy as _
from allauth.account.models import EmailAddress

from .models import User


class EmailAddressInline(admin.StackedInline):
    model = EmailAddress
    extra = 0
    readonly_fields = ['email']

    def has_add_permission(self, *args, **kwargs):
        return False


class UserCreationForm(BaseUserCreationForm):
    email = forms.EmailField(label=_('Email'), max_length=254, required=True)

    def save(self, commit=True):
        """
        automatically creates new email for new users
        added via the django-admin interface
        """
        user = super(UserCreationForm, self).save(commit)
        return user


class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    readonly_fields = ['last_login', 'date_joined']
    inlines = [EmailAddressInline]

    def get_inline_instances(self, request, obj=None):
        if obj:
            return super(UserAdmin, self).get_inline_instances(request, obj)
        return []

    def save_model(self, request, obj, form, change):
        """
        automatically creates email addresses for users
        added/changed via the django-admin interface
        """
        super(UserAdmin, self).save_model(request, obj, form, change)
        EmailAddress.objects.add_email(request,
                                       user=obj,
                                       email=obj.email,
                                       confirm=True,
                                       signup=True)


base_fields = list(UserAdmin.fieldsets[1][1]['fields'])
additional_fields = ['bio', 'url', 'company', 'location']
UserAdmin.fieldsets[1][1]['fields'] = base_fields + additional_fields
UserAdmin.add_fieldsets[0][1]['fields'] = ('username', 'email', 'password1', 'password2')


admin.site.register(User, UserAdmin)
