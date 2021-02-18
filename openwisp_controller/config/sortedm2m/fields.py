"""
Customized sortedm2m field to support required templates
"""
from itertools import chain

from django import forms
from django.template.loader import render_to_string
from django.utils.encoding import force_str
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from sortedm2m.fields import SortedManyToManyField as BaseSortedManyToManyField
from sortedm2m.forms import (
    SortedCheckboxSelectMultiple as BaseSortedCheckboxSelectMultiple,
)
from sortedm2m.forms import SortedMultipleChoiceField as BaseSortedMultipleChoiceField


class SortedCheckboxSelectMultiple(BaseSortedCheckboxSelectMultiple):
    def render(
        self, name, value, attrs=None, choices=(), renderer=None
    ):  # pylint: disable=arguments-differ
        if value is None:
            value = []
        has_id = attrs and 'id' in attrs
        final_attrs = self.build_attrs(attrs, name=name)

        # Normalize to strings
        str_values = [force_str(v) for v in value]

        selected = []
        unselected = []

        for i, (option_value, option_label) in enumerate(chain(self.choices, choices)):
            # If an ID attribute was given, add a numeric index as a suffix,
            # so that the checkboxes don't all have the same ID attribute.
            if has_id:
                final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], i))
                label_for = ' for="%s"' % conditional_escape(final_attrs['id'])
            else:
                label_for = ''

            cb = forms.CheckboxInput(
                final_attrs, check_test=lambda value: value in str_values
            )
            cb, option_label, option_value = self.modify_checkbox(
                cb, option_label, option_value
            )
            option_value = force_str(option_value)
            rendered_cb = cb.render(name, option_value)
            option_label = conditional_escape(force_str(option_label))
            item = {
                'label_for': label_for,
                'rendered_cb': rendered_cb,
                'option_label': option_label,
                'option_value': option_value,
            }
            if option_value in str_values:
                selected.append(item)
            else:
                unselected.append(item)

        # Reorder `selected` array according str_values which is a
        # set of `option_value`s in the order they should be shown on screen
        ordered = []
        for s in str_values:
            for select in selected:
                if s == select['option_value']:
                    ordered.append(select)
        selected = ordered

        html = render_to_string(
            'sortedm2m/sorted_checkbox_select_multiple_widget.html',
            {'selected': selected, 'unselected': unselected},
        )
        return mark_safe(html)

    def modify_checkbox(self, cb, option_label, option_value):
        if option_value.instance.required:
            cb.attrs['disabled'] = 'disabled'
            cb.attrs['checked'] = 'checked'
            option_label = f'{option_label} (required)'
        return cb, option_label, option_value


class SortedMultipleChoiceField(BaseSortedMultipleChoiceField):
    widget = SortedCheckboxSelectMultiple


class SortedManyToManyField(BaseSortedManyToManyField):
    def formfield(self, **kwargs):
        defaults = {}
        if self.sorted:
            defaults['form_class'] = SortedMultipleChoiceField
        defaults.update(kwargs)
        return super().formfield(**defaults)
