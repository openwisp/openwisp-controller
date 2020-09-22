import logging

from ..ssh import Ssh

logger = logging.getLogger(__name__)


class OpenWrt(Ssh):
    def update_config(self):
        _, exit_code = self.exec_command(
            'test -f /tmp/openwisp/applying_conf', exit_codes=[0, 1]
        )
        if exit_code == 1:
            self.exec_command('/etc/init.d/openwisp_config restart')
        else:
            logger.info('Configuration already being applied')
