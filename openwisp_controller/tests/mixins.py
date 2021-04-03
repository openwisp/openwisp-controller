# Mixins used for unit tests of openwisp_controller


class GetEditFormInlineMixin(object):
    def _get_org_edit_form_inline_params(self, user, org):
        params = super()._get_org_edit_form_inline_params(user, org)
        params.update(
            {
                # config inline
                'config_settings-TOTAL_FORMS': 0,
                'config_settings-INITIAL_FORMS': 0,
                'config_settings-MIN_NUM_FORMS': 0,
                'config_settings-MAX_NUM_FORMS': 0,
            }
        )
        return params

    def _get_user_edit_form_inline_params(self, user, organization):
        params = super()._get_user_edit_form_inline_params(user, organization)
        params.update(
            {
                'notificationsetting_set-TOTAL_FORMS': 0,
                'notificationsetting_set-INITIAL_FORMS': 0,
                'notificationsetting_set-MIN_NUM_FORMS': 0,
                'notificationsetting_set-MAX_NUM_FORMS': 0,
            }
        )
        return params
