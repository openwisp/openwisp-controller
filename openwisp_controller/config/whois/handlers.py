from django.db import transaction

from .service import WhoIsService


# Remove the related WhoIs record for that ip from db and cache
# If other active devices are linked to it, then new lookup will
# be triggered for them.
def device_whois_info_delete_handler(instance, **kwargs):
    transaction.on_commit(
        lambda: WhoIsService.delete_whois_record.delay(instance.last_ip)
    )
