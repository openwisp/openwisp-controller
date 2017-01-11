from django_netjsonconfig.tests import (CreateConfigMixin,
                                        CreateTemplateMixin,
                                        CreateVpnMixin)
from ...pki.tests import TestPkiMixin


class TestVpnX509Mixin(CreateVpnMixin, TestPkiMixin):
    pass


class CreateConfigTemplateMixin(CreateTemplateMixin, CreateConfigMixin):
    pass
