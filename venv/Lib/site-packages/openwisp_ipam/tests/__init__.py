import json
import os

from openwisp_users.tests.utils import TestOrganizationMixin
from swapper import load_model

Subnet = load_model("openwisp_ipam", "Subnet")
IpAddress = load_model("openwisp_ipam", "IpAddress")
Organization = load_model("openwisp_users", "Organization")


class FileMixin(object):
    def _get_path(self, file):
        d = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(d, file)


class CreateModelsMixin(TestOrganizationMixin):
    def _get_extra_fields(self, **kwargs):
        if "organization" not in kwargs:
            kwargs["organization"] = self._get_org()
        return kwargs

    def _create_subnet(self, **kwargs):
        options = dict(
            name="test subnet",
            subnet="",
            description="",
        )
        options.update(self._get_extra_fields(**kwargs))
        options.update(kwargs)
        instance = Subnet(**options)
        instance.full_clean()
        instance.save()
        return instance

    def _create_ipaddress(self, **kwargs):
        options = dict(
            ip_address="",
            description="",
        )
        options.update(kwargs)
        instance = IpAddress(**options)
        instance.full_clean()
        instance.save()
        return instance


class PostDataMixin(object):
    def _post_data(self, **kwargs):
        org = Organization.objects.get_or_create(name="test-organization")
        kwargs["organization"] = str(org[0].pk)
        return json.dumps(dict(kwargs))
