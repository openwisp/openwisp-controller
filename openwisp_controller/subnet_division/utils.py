def get_subnet_division_config_context(config):
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
