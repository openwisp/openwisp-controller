from openwisp_users import admin
from openwisp_users.utils import (
    usermodel_add_form,
    usermodel_change_form,
    usermodel_list_and_search,
)

additional_fields = [
    [2, 'social_security_number'],
]

usermodel_add_form(admin.UserAdmin, additional_fields)
usermodel_change_form(admin.UserAdmin, additional_fields)
usermodel_list_and_search(admin.UserAdmin, additional_fields)
