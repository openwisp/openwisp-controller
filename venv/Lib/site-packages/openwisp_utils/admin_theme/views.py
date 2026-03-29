from admin_auto_filters.views import AutocompleteJsonView as BaseAutocompleteJsonView
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse


class AutocompleteJsonView(BaseAutocompleteJsonView):
    admin_site = None

    def get_empty_label(self):
        return "-"

    def get_allow_null(self):
        return True

    def get(self, request, *args, **kwargs):
        (
            self.term,
            self.model_admin,
            self.source_field,
            _,
        ) = self.process_request(request)

        if not self.has_perm(request):
            raise PermissionDenied

        self.support_reverse_relation()
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        # Add option for filtering objects with None field.
        results = []
        empty_label = self.get_empty_label()
        if (
            getattr(self.source_field, "null", False)
            and self.get_allow_null()
            and not getattr(self.source_field, "_get_limit_choices_to_mocked", False)
            and not self.term
            or self.term == empty_label
        ):
            # The select2 library requires data in a specific format
            # https://select2.org/data-sources/formats.
            # select2 does not render option with blank "id" (i.e. '').
            # Therefore, "null" is used here for "id".
            results += [{"id": "null", "text": empty_label}]
        results += [
            {"id": str(obj.pk), "text": self.display_text(obj)}
            for obj in context["object_list"]
        ]
        return JsonResponse(
            {
                "results": results,
                "pagination": {"more": context["page_obj"].has_next()},
            }
        )

    def support_reverse_relation(self):
        if not hasattr(self.source_field, "get_limit_choices_to"):
            self.source_field._get_limit_choices_to_mocked = True

            def get_choices_mock():
                return {}

            self.source_field.get_limit_choices_to = get_choices_mock
