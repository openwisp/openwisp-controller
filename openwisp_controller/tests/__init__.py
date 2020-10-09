from django.conf import settings

from openwisp_utils.utils import deepcopy


def _get_updated_templates_settings(context_processors=[]):
    template_settings = deepcopy(settings.TEMPLATES[0])
    if len(context_processors):
        template_settings['OPTIONS']['context_processors'].extend(context_processors)
    else:
        template_settings['OPTIONS']['context_processors'].append(
            'openwisp_controller.context_processors.controller_api_settings'
        )
    return [template_settings]
