import copy
import html

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count
from swapper import load_model

from ..utils import SortedOrderedDict

DASHBOARD_CHARTS = SortedOrderedDict()
DASHBOARD_TEMPLATES = SortedOrderedDict()


def _validate_chart_config(config):
    query_params = config.get("query_params", None)
    quick_link = config.get("quick_link", None)

    assert query_params is not None
    assert "name" in config
    assert "app_label" in query_params
    assert "model" in query_params
    assert (
        "filter" in query_params
        or "group_by" in query_params
        or "annotate" in query_params
    )
    assert not ("group_by" in query_params and "annotate" in query_params)
    if "annotate" in query_params:
        assert "filters" in config, "filters must be defined when using annotate"
    if quick_link:
        assert "url" in quick_link, "url must be defined when using quick_link"
        assert "label" in quick_link, "label must be defined when using quick_link"
        if "custom_css_classes" in quick_link:
            assert isinstance(quick_link["custom_css_classes"], list) or isinstance(
                quick_link["custom_css_classes"], tuple
            ), "custom_css_classes must be either a list or a tuple"
    return config


def register_dashboard_chart(position, config):
    """Registers a dashboard chart:

    The position argument indicates the order. The config argument
    indicates the chart configuration details.
    """
    if not isinstance(position, int):
        raise ImproperlyConfigured("Dashboard chart position should be of type `int`.")
    if not isinstance(config, dict):
        raise ImproperlyConfigured("Dashboard chart config should be of type `dict`.")
    if position in DASHBOARD_CHARTS:
        raise ImproperlyConfigured(
            f'Cannot register chart {config["name"]}. '
            f'Another chart is already registered at position n. "{position}": '
            f'{DASHBOARD_CHARTS[position]["name"]}'
        )
    validated_config = _validate_chart_config(config)
    DASHBOARD_CHARTS.update({position: validated_config})


def unregister_dashboard_chart(name):
    """Un-registers a dashboard chart."""
    if not isinstance(name, str):
        raise ImproperlyConfigured("Dashboard chart name should be type `str`")

    for key, value in DASHBOARD_CHARTS.items():
        if value["name"] == name:
            key_to_remove = key
            break
    else:
        raise ImproperlyConfigured(f"No such chart: {name}")

    DASHBOARD_CHARTS.pop(key_to_remove)


def _validate_template_config(config):
    assert "template" in config
    return config


def register_dashboard_template(
    position, config, extra_config=None, after_charts=False
):
    """Registers a dashboard HTML template."""
    if not isinstance(position, int):
        raise ImproperlyConfigured(
            "Dashboard template position should be of type `int`."
        )
    if not isinstance(config, dict):
        raise ImproperlyConfigured(
            "Dashboard template config parameters should be of type `dict`."
        )
    if extra_config and not isinstance(extra_config, dict):
        raise ImproperlyConfigured(
            "Dashboard template extra_config parameters should be of type `dict`."
        )

    if position in DASHBOARD_TEMPLATES:
        raise ImproperlyConfigured(
            f'Cannot register template {config["template"]}. '
            f'Another template is already registered at position n. "{position}": '
            f'{DASHBOARD_TEMPLATES[position][0]["template"]}'
        )
    validated_config = _validate_template_config(config)
    DASHBOARD_TEMPLATES.update(
        {position: [validated_config, extra_config, after_charts]}
    )


def unregister_dashboard_template(path):
    """Un-registers a dashboard template."""
    if not isinstance(path, str):
        raise ImproperlyConfigured("Dashboard template path should be type `str`")

    for key, value in DASHBOARD_TEMPLATES.items():
        if value[0]["template"] == path:
            key_to_remove = key
            break
    else:
        raise ImproperlyConfigured(f"No such template: {path}")

    DASHBOARD_TEMPLATES.pop(key_to_remove)


def get_dashboard_context(request):
    """Loads dashboard context for the admin index view."""
    context = {"is_popup": False, "has_permission": True, "dashboard_enabled": True}
    config = copy.deepcopy(DASHBOARD_CHARTS)

    for key, value in config.items():
        query_params = value["query_params"]
        app_label = query_params["app_label"]
        model_name = query_params["model"]
        qs_filter = query_params.get("filter")
        group_by = query_params.get("group_by")
        annotate = query_params.get("annotate")
        aggregate = query_params.get("aggregate")
        org_field = query_params.get("organization_field")
        default_org_field = "organization_id"

        labels_i18n = value.get("labels")
        # HTML escape labels defined in configuration to prevent breaking the JS
        if labels_i18n:
            for label_key, label_value in labels_i18n.items():
                labels_i18n[label_key] = html.escape(label_value)

        try:
            model = load_model(app_label, model_name)
        except ImproperlyConfigured:
            raise ImproperlyConfigured(
                f"Error adding dashboard element {key}."
                f"REASON: {app_label}.{model_name} could not be loaded."
            )

        qs = model.objects
        if qs_filter:
            for field, lookup_value in qs_filter.items():
                if callable(lookup_value):
                    qs_filter[field] = lookup_value()
            qs = qs.filter(**qs_filter)

        # Filter query according to organization of user
        if not request.user.is_superuser and (
            org_field or hasattr(model, default_org_field)
        ):
            org_field = org_field or default_org_field
            qs = qs.filter(**{f"{org_field}__in": request.user.organizations_managed})

        annotate_kwargs = {}
        if group_by:
            annotate_kwargs["count"] = Count(group_by)
            qs = qs.values(group_by)
        if annotate:
            annotate_kwargs.update(annotate)

        qs = qs.annotate(**annotate_kwargs)

        if aggregate:
            qs = qs.aggregate(**aggregate)

        # Organize data for representation using Plotly.js
        # Create a list of labels and values from the queryset
        # where each element in the form of
        # {group_by : '<label>', 'count': <value>}
        values = []
        labels = []
        colors = []
        filters = []
        main_filters = []
        url_operator = "?"
        value["target_link"] = f"/admin/{app_label}/{model_name}/"
        if value.get("main_filters"):
            for main_filter_key, main_filter_value in value["main_filters"].items():
                if callable(main_filter_value):
                    main_filter_value = str(main_filter_value())
                main_filters.append(f"{main_filter_key}={main_filter_value}")

            value["target_link"] = "{path}?{main_filters}".format(
                path=value["target_link"], main_filters="&".join(main_filters)
            )
            value.pop("main_filters", None)
            url_operator = "&"

        if group_by:
            for obj in qs:
                # avoid showing an empty "None" label
                if obj["count"] == 0:
                    continue
                qs_key = str(obj[group_by])
                label = qs_key
                # get human readable label if predefined labels are available
                # otherwise use the result got from the DB
                if labels_i18n and qs_key in labels_i18n:
                    # store original label as filter, but only
                    # if we have more than the empty default label defined
                    filters.append(label)
                    label = labels_i18n[qs_key]
                else:
                    # HTML escape labels coming from values in the DB
                    # to avoid possible XSS attacks caused by
                    # malicious DB values set by users
                    label = html.escape(label)
                labels.append(label)
                # use predefined colors if available,
                # otherwise the JS lib will choose automatically
                if value.get("colors") and qs_key in value["colors"]:
                    colors.append(value["colors"][qs_key])
                values.append(obj["count"])
            value["target_link"] = "{path}{url_operator}{group_by}__exact=".format(
                path=value["target_link"], url_operator=url_operator, group_by=group_by
            )

        if aggregate:
            for qs_key, qs_value in qs.items():
                if not qs_value:
                    continue
                labels.append(labels_i18n[qs_key])
                values.append(qs_value)
                colors.append(value["colors"][qs_key])
                if value.get("filters"):
                    filters.append(value["filters"][qs_key])
            if value.get("filters"):
                value["target_link"] = "{path}{url_operator}{filter_key}=".format(
                    url_operator=url_operator,
                    path=value["target_link"],
                    filter_key=value["filters"]["key"],
                )

        value["query_params"] = {"values": values, "labels": labels}
        value["colors"] = colors
        if filters:
            value["filters"] = filters

    # dashboard templates
    extra_config = {}
    templates_before_charts = []
    templates_after_charts = []
    css = []
    js = []
    for _, template_config in DASHBOARD_TEMPLATES.items():
        if template_config[2]:
            templates_after_charts.append(template_config[0]["template"])
        else:
            templates_before_charts.append(template_config[0]["template"])
        if "css" in template_config[0]:
            css += list(template_config[0]["css"])
        if "js" in template_config[0]:
            js += list(template_config[0]["js"])
        if template_config[1]:
            extra_config.update(template_config[1])

    context.update(
        {
            "dashboard_charts": dict(config),
            "dashboard_templates_before_charts": templates_before_charts,
            "dashboard_templates_after_charts": templates_after_charts,
            "dashboard_css": css,
            "dashboard_js": js,
        }
    )
    context.update(extra_config)
    return context
