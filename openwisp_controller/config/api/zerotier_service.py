import requests
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from requests.exceptions import ConnectionError, RequestException, Timeout

REQUEST_TIMEOUT = 5


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

    def __init__(self, host, token, subnet=''):
        self.host = host
        self.token = token
        self.subnet = subnet
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
        ip_end = str(self.subnet.broadcast_address)
        ip_start = str(next(self.subnet.hosts()))
        config['ipAssignmentPools'] = [{"ipRangeEnd": ip_end, "ipRangeStart": ip_start}]
        return config

    def join_network(self, network_id):
        url = f'{self.url}/network/{network_id}'
        response = requests.post(
            url, json={}, headers=self.headers, timeout=REQUEST_TIMEOUT
        )
        return response

    def leave_network(self, network_id):
        url = f'{self.url}/network/{network_id}'
        response = requests.delete(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
        return response

    def update_network_member(self, node_id, network_id, member_ip):
        url = f'{self.url}/controller/network/{network_id}/member/{node_id}'
        # Authorize and assign ip to the network member
        response = requests.post(
            url,
            json={'authorized': True, 'ipAssignments': [str(member_ip)]},
            headers=self.headers,
            timeout=5,
        )
        return response

    def leave_network_member(self, node_id, network_id):
        url = f'{self.url}/controller/network/{network_id}/member/{node_id}'
        response = requests.delete(url, headers=self.headers, timeout=5)
        return response

    def get_node_status(self):
        url = f'{self.url}/status'
        try:
            response = requests.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            return response
        except (Timeout, ConnectionError) as err:
            raise ValidationError(
                {
                    'host': _(
                        'Failed to connect to the ZeroTier controller, Error: {0}'
                    ).format(err)
                }
            )

    def create_network(self, node_id, config):
        url = f"{self.url}{self._get_endpoint('network', 'create', node_id)}"
        config = self._add_routes_and_ip_assignment(config)
        try:
            response = requests.post(
                url, json=config, headers=self.headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            network_config = self._get_repsonse(response.json())
            return network_config
        except RequestException as exc:
            raise ValidationError(
                _('Failed to create ZeroTier network, Error: {0}').format(exc)
            )

    def update_network(self, config, network_id):
        url = f"{self.url}{self._get_endpoint('network', 'update', network_id)}"
        config = self._add_routes_and_ip_assignment(config)
        response = requests.post(
            url, json=config, headers=self.headers, timeout=REQUEST_TIMEOUT
        )
        return response, self._get_repsonse(response.json())

    def delete_network(self, network_id):
        url = f"{self.url}{self._get_endpoint('network', 'delete', network_id)}"
        response = requests.delete(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
        return response
