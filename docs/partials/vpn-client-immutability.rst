.. important::

    VPN clients are immutable: once OpenWISP has provisioned the VPN
    tunnel of a device (x509 certificate, IP address, cryptographic keys),
    the generated VPN client cannot be modified anymore. The only
    exception is the provisioned IP address, which may be updated
    internally by OpenWISP (e.g.: by :doc:`subnet division rules
    </controller/user/subnet-division-rules>`).

    To re-provision the VPN tunnel of a device, remove the VPN client
    template from the device configuration, save the device, then add the
    template again: the old VPN client is deleted and a new one is
    provisioned from scratch.
