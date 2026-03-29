from django import template
from django.template.defaultfilters import stringfilter
from django.template.loader import get_template

register = template.Library()


@register.simple_tag
def ow_create_filter(cl, spec, total_filters):
    tpl = get_template(spec.template)
    choices = list(spec.choices(cl))
    selected_choice = None
    for choice in choices:
        if choice["selected"]:
            selected_choice = choice["display"]
    return tpl.render(
        {
            "title": spec.title,
            "choices": list(spec.choices(cl)),
            "spec": spec,
            "show_button": total_filters > 4,
            "selected_choice": selected_choice,
        }
    )


@register.filter
@stringfilter
def join_string(value):
    """Can be used to join strings with "-" to make id or class."""
    return value.lower().replace(" ", "-")
