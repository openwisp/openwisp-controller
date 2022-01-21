def get_subnet_division_config_context(config):
    """
    Returns SubnetDivision context containing subnet
    and IP address provisioned for the "config" object.

    This function is called by "Config.get_context" method.
    """
    context = {}
    qs = config.subnetdivisionindex_set.values(
        'keyword', 'subnet__subnet', 'ip__ip_address'
    )
    for entry in qs:
        if entry['ip__ip_address'] is None:
            context[entry['keyword']] = str(entry['subnet__subnet'])
        else:
            context[entry['keyword']] = str(entry['ip__ip_address'])
    prefixlen = (
        config.subnetdivisionindex_set.select_related('rule')
        .values('rule__label', 'rule__size')
        .first()
    )
    if prefixlen:
        context[f'{prefixlen["rule__label"]}_prefixlen'] = str(prefixlen['rule__size'])
    return context


def subnet_division_vpnclient_auto_ip(vpn_client):
    """
    Overrides the the default behavior of VpnClient.auto_ip
    which automatically assigns an IP to the VpnClient.
    This assignment is handled by SubnetDivision rule,
    so we need to skip it here.

    This function is called by "VpnClient._auto_ip" method.
    """
    return (
        vpn_client.vpn.subnet
        and vpn_client.vpn.subnet.subnetdivisionrule_set.filter(
            organization_id=vpn_client.config.device.organization,
            type=(
                'openwisp_controller.subnet_division.rule_types.'
                'vpn.VpnSubnetDivisionRuleType'
            ),
        ).exists()
    )
