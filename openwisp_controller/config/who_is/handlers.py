from django.core.cache import cache
from django.db import transaction

from .service import WhoIsService


# Remove the related WhoIs record for that ip from db and cache
# If other active devices are linked to it, then new lookup will
# be triggered for them.
def device_who_is_info_delete_handler(instance, **kwargs):
    transaction.on_commit(
        lambda: WhoIsService.delete_who_is_record.delay(instance.last_ip)
    )


def invalidate_org_settings_cache(instance, **kwargs):
    org_pk = instance.organization_id
    cache.delete(WhoIsService.ORG_SETTINGS_CACHE_KEY.format(org_pk=org_pk))
