from swapper import load_model

from ..tests.utils import CreateConfigMixin

WhoIsInfo = load_model("config", "WhoIsInfo")


class CreateWhoIsMixin(CreateConfigMixin):
    def _create_who_is_info(self, **kwargs):
        options = dict(
            ip_address="172.217.22.14",
            address={
                "city": "Mountain View",
                "country": "United States",
                "continent": "North America",
                "postal": "94043",
            },
            asn="15169",
            isp="Google LLC",
            timezone="America/Los_Angeles",
            cidr="172.217.22.0/24",
        )

        options.update(kwargs)
        w = WhoIsInfo(**options)
        w.full_clean()
        w.save()
        return w
