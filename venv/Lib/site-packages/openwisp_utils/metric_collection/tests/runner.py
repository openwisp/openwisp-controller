from unittest.mock import patch

import requests
from openwisp_utils import utils
from openwisp_utils.tests import TimeLoggingTestRunner

success_response = requests.Response()
success_response.status_code = 204


class MockRequestPostRunner(TimeLoggingTestRunner):
    """This runner ensures that usage metrics are not sent in development when running tests."""

    pass

    def setup_databases(self, **kwargs):
        utils.requests.Session._original_post = utils.requests.Session.post
        with patch.object(
            utils.requests.Session, "post", return_value=success_response
        ):
            return super().setup_databases(**kwargs)

    def run_suite(self, suite, **kwargs):
        with patch.object(
            utils.requests.Session, "post", return_value=success_response
        ):
            return super().run_suite(suite)
