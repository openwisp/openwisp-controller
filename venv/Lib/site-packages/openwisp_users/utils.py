from django.conf import settings

if "reversion" in settings.INSTALLED_APPS:  # pragma: no cover
    from reversion.admin import VersionAdmin as BaseModelAdmin
else:
    from django.contrib.admin import ModelAdmin as BaseModelAdmin


class BaseAdmin(BaseModelAdmin):
    history_latest_first = True


def usermodel_add_form(model, additional_fields):
    """
    Read:
    https://github.com/openwisp/openwisp-users/blob/master/README.rst#usermodel_add_form
    """

    for field in additional_fields:
        modelMeta = model.add_form.Meta
        # Add form fieldsets
        add_fieldsets = modelMeta.fieldsets[0][1]["fields"][:]
        modelMeta.fieldsets[0][1]["fields"] = (
            add_fieldsets[: field[0]] + [field[1]] + add_fieldsets[field[0] :]
        )
        # Add form fieldsets_superuser
        add_fieldsets_superuser = modelMeta.fieldsets_superuser[0][1]["fields"][:]
        modelMeta.fieldsets_superuser[0][1]["fields"] = (
            add_fieldsets_superuser[: field[0]]
            + [field[1]]
            + add_fieldsets_superuser[field[0] :]
        )


def usermodel_change_form(model, additional_fields):
    """
    Read:
    https://github.com/openwisp/openwisp-users/blob/master/README.rst#usermodel_change_form
    """

    # Change form fieldsets
    for field in additional_fields:
        fieldsets = model.fieldsets[1][1]["fields"][:]
        model.fieldsets[1][1]["fields"] = (
            fieldsets[: field[0]] + [field[1]] + fieldsets[field[0] :]
        )


def usermodel_list_and_search(model, additional_fields):
    """
    Read:
    https://github.com/openwisp/openwisp-users/blob/master/README.rst#usermodel_list_and_search
    """

    # Change form fieldsets
    for field in additional_fields:
        displays = model.list_display[:]
        model.list_display = displays[: field[0]] + [field[1]] + displays[field[0] :]
        model.search_fields += (field[1],)
