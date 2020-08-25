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

    def reboot(self):
        return self.exec_command('reboot')

    def change_password(self, password, confirm_password, user='root'):
        return self.exec_command(
            f'echo -e "{password}\n{confirm_password}" | passwd {user}'
        )


class OpenWisp1(Ssh):
    """
    Dummy legacy backend.
    Used for migrating OpenWISP 1 systems to OpenWISP 2.
    """

    def update_config(self):  # pragma: no cover
        pass
