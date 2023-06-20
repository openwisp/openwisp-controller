import requests
from django.core.exceptions import ValidationError


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

    def __init__(self, host, token):
        self.host = host
        self.token = token
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
        ]
        for field in _redundant_fields:
            if field in repsonse.keys():
                del repsonse[field]
        return repsonse

    def create_network(self, config):
        # Call /status first to obtain
        # the `node_id` of the controller
        url = f'{self.url}/status'
        response = requests.get(url, headers=self.headers)
        node_id = response.json()['address']
        url = f"{self.url}{self._get_endpoint('network', 'create', node_id)}"
        response = requests.post(url, json=config, headers=self.headers, timeout=5)
        if response.status_code != 200:
            raise ValidationError(
                {
                    'ZerotierServiceAPI create network error': (
                        f'({response.status_code}) {response.reason}'
                    )
                }
            )
        return self._get_repsonse(response.json())

    def update_network(self, config):
        network_id = config.get('id')
        url = f"{self.url}{self._get_endpoint('network', 'update', network_id)}"
        response = requests.post(url, json=config, headers=self.headers, timeout=5)
        if response.status_code != 200:
            raise ValidationError(
                {
                    'ZerotierServiceAPI create network error': (
                        f'({response.status_code}) {response.reason}'
                    )
                }
            )
        return self._get_repsonse(response.json())

    def delete_network(self, network_id):
        url = f"{self.url}{self._get_endpoint('network', 'delete', network_id)}"
        print(url)
        response = requests.delete(url, headers=self.headers)
        if response.status_code not in (200, 404):
            raise ValidationError(
                {
                    'ZerotierServiceAPI delete network error': (
                        f'({response.status_code}) {response.reason}'
                    )
                }
            )
