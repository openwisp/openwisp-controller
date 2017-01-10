from django_netjsonconfig.tests import CreateVpnMixin
from ...pki.tests import TestPkiMixin


class TestVpnX509Mixin(CreateVpnMixin, TestPkiMixin):
    pass
