import requests
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ZerotierService:
    def _get_endpoint(self, property, operation, id):
        _API_ENDPOINTS = {
            'network': {
                'create': f'/controller/network/{id}______',
                'get': f'/controller/network/{id}',
                'update': f'/controller/network/{id}',
                'delete': f'/controller/network/{id}',
            }
        }
        return _API_ENDPOINTS.get(property).get(operation)

    def __init__(self, host, token, subnet='', ip=''):
        self.host = host
        self.token = token
        self.subnet = subnet
        self.ip = str(ip)
        self.url = f'http://{host}'
        self.headers = {
            'X-ZT1-Auth': self.token,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def _get_repsonse(self, repsonse):
        # remove redundant fields from the response
        _redundant_fields = [
            'authTokens',
            'authorizationEndpoint',
            'clientId',
            'rulesSource',
            'ssoEnabled',
            'creationTime',
            'name',
            'nwid',
            'objtype',
            'revision',
            'routes',
            'ipAssignmentPools',
        ]
        for field in _redundant_fields:
            if field in repsonse.keys():
                del repsonse[field]
        return repsonse

    def _add_routes_and_ip_assignment(self, config):
        config['routes'] = [{'target': str(self.subnet), 'via': ''}]
        try:
            ip_end = str(self.subnet[-2])
            ip_start = str(self.subnet[1])
        # In case of prefix length 32 (ipv4)
        # or 128 (ipv6) only single host is available
        except IndexError:
            ip_end = str(self.subnet[0])
            ip_start = str(self.subnet[0])

        config['ipAssignmentPools'] = [{"ipRangeEnd": ip_end, "ipRangeStart": ip_start}]
        return config

    def join_network(self, network_id):
        url = f'{self.url}/network/{network_id}'
        response = requests.post(url, json={}, headers=self.headers, timeout=5)
        return response

    def leave_network(self, network_id):
        url = f'{self.url}/network/{network_id}'
        response = requests.delete(url, headers=self.headers, timeout=5)
        return response

    def update_network_member(self, node_id, network_id):
        url = f'{self.url}/controller/network/{network_id}/member/{node_id}'
        # Authorize and assign ip to the network member
        response = requests.post(
            url,
            json={'authorized': True, 'ipAssignments': [self.ip]},
            headers=self.headers,
            timeout=5,
        )
        return response

    def get_node_status(self):
        url = f'{self.url}/status'
        response = requests.get(url, headers=self.headers, timeout=5)
        return response

    def create_network(self, node_id, config):
        url = f"{self.url}{self._get_endpoint('network', 'create', node_id)}"
        config = self._add_routes_and_ip_assignment(config)
        response = requests.post(url, json=config, headers=self.headers, timeout=5)
        network_config = self._get_repsonse(response.json())
        if response.status_code != 200:
            raise ValidationError(
                _(
                    'Failed to create ZeroTier network '
                    '(error: {0}, status code: {1})'
                ).format(response.reason, response.status_code)
            )
        return network_config

    def update_network(self, config, network_id):
        url = f"{self.url}{self._get_endpoint('network', 'update', network_id)}"
        config = self._add_routes_and_ip_assignment(config)
        response = requests.post(url, json=config, headers=self.headers, timeout=5)
        return response, self._get_repsonse(response.json())

    def delete_network(self, network_id):
        url = f"{self.url}{self._get_endpoint('network', 'delete', network_id)}"
        response = requests.delete(url, headers=self.headers, timeout=5)
        return response
