from sortedm2m.forms import (
    SortedCheckboxSelectMultiple as BaseSortedCheckboxSelectMultiple,
)
from sortedm2m.forms import SortedMultipleChoiceField as BaseSortedMultipleChoiceField


class SortedCheckboxSelectMultiple(BaseSortedCheckboxSelectMultiple):
    class Media(BaseSortedCheckboxSelectMultiple.Media):
        # The django-sortedm2m library has a bug when the widget is
        # use in StackedInline Admin, see
        # https://github.com/jazzband/django-sortedm2m/pull/213
        # The workaround in sortedm2m/patch_sortedm2m.js fixes the bug.
        # TODO: Remove this workaround when a new version of django-sortedm2m
        # is released.
        js = (
            'admin/js/jquery.init.js',
            'sortedm2m/widget.js',
            'sortedm2m/jquery-ui.js',
            'sortedm2m/patch_sortedm2m.js',
        )


class SortedMultipleChoiceField(BaseSortedMultipleChoiceField):
    widget = SortedCheckboxSelectMultiple
