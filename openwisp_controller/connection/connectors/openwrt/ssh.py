from ..ssh import Ssh


class OpenWrt(Ssh):
    def update_config(self):
        self.exec_command('/etc/init.d/openwisp_config restart')
