from django.conf import settings

SUBNET_DIVISION_TYPES = getattr(
    settings,
    'OPENWISP_CONTROLLER_SUBNET_DIVISION_TYPES',
    (
        (
            (
                'openwisp_controller.subnet_division.rule_types.'
                'vpn.VpnSubnetDivisionRuleType'
            ),
            'VPN',
        ),
        (
            (
                'openwisp_controller.subnet_division.rule_types.'
                'device.DeviceSubnetDivisionRuleType'
            ),
            'Device',
        ),
    ),
)

HIDE_GENERATED_SUBNETS = getattr(
    settings,
    'OPENWISP_CONTROLLER_HIDE_AUTOMATICALLY_GENERATED_SUBNETS_AND_IPS',
    False,
)
