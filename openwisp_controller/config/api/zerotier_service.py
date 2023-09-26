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
        """
        Adds ZeroTier network routes
        and IP assignmentpools through OpenWISP subnet

        Params:
            config (dict): ZeroTier network config dict
        """
        config['routes'] = [{'target': str(self.subnet), 'via': ''}]
        ip_end = str(self.subnet.broadcast_address)
        ip_start = str(next(self.subnet.hosts()))
        config['ipAssignmentPools'] = [{"ipRangeEnd": ip_end, "ipRangeStart": ip_start}]
        return config

    def get_node_status(self):
        """
        Fetches the status of the running ZeroTier controller
        This method is used for host validation during VPN creation
        """
        url = f'{self.url}/status'
        try:
            response = requests.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            return response
        except (Timeout, ConnectionError) as e:
            raise ValidationError(
                {
                    'host': _(
                        'Failed to connect to the ZeroTier controller, Error: {0}'
                    ).format(e)
                }
            )

    def join_network(self, network_id):
        """
        Adds ZeroTier Controller to the specified network

        Params:
            network_id (str): ID of the network to join
        """
        url = f'{self.url}/network/{network_id}'
        response = requests.post(
            url, json={}, headers=self.headers, timeout=REQUEST_TIMEOUT
        )
        return response

    def leave_network(self, network_id):
        """
        Removes ZeroTier Controller from the specified network

        Params:
            network_id (str): ID of the network to leave
        """
        url = f'{self.url}/network/{network_id}'
        response = requests.delete(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
        return response

    def create_network(self, node_id, config):
        """
        Creates a new network in the ZeroTier Controller

        Params:
            node_id (str): ID of the controller node
            config (dict): Configuration of the new network

        Returns:
            network_config(dict): Filtered response from the ZeroTier Controller API
        """
        url = f"{self.url}{self._get_endpoint('network', 'create', node_id)}"
        config = self._add_routes_and_ip_assignment(config)
        try:
            response = requests.post(
                url, json=config, headers=self.headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            network_config = self._get_repsonse(response.json())
            return network_config
        except RequestException as e:
            raise ValidationError(
                _('Failed to create ZeroTier network, Error: {0}').format(e)
            )

    def update_network(self, config, network_id):
        """
        Update configuration of an existing ZeroTier Controller network

        Params:
            config (dict): New configuration data for the network
            network_id (str): ID of the network to update
        """
        url = f"{self.url}{self._get_endpoint('network', 'update', network_id)}"
        config = self._add_routes_and_ip_assignment(config)
        response = requests.post(
            url, json=config, headers=self.headers, timeout=REQUEST_TIMEOUT
        )
        return response, self._get_repsonse(response.json())

    def delete_network(self, network_id):
        """
        Deletes ZeroTier Controller network

        Params:
            network_id (str): ID of the ZeroTier network to be deleted
        """
        url = f"{self.url}{self._get_endpoint('network', 'delete', network_id)}"
        response = requests.delete(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
        return response

    def update_network_member(self, node_id, network_id, member_ip):
        """
        Update ZeroTier Network Member Configuration

        This method is currently used to authorize, enable the bridge
        and assign an IP address to a network member

        Params:
            node_id (str): Node ID of the network member
            network_id (str): Network ID to which the member belongs
            member_ip (str): IP address to be assigned to the network member
        """
        url = f'{self.url}/controller/network/{network_id}/member/{node_id}'
        response = requests.post(
            url,
            json={
                'authorized': True,
                'activeBridge': True,
                'ipAssignments': [str(member_ip)],
            },
            headers=self.headers,
            timeout=5,
        )
        return response

    def remove_network_member(self, node_id, network_id):
        """
        Remove a member from ZeroTier network

        Params:
            node_id (str): ID of the network member
            network_id (str): ID of the ZeroTier network
        """
        url = f'{self.url}/controller/network/{network_id}/member/{node_id}'
        response = requests.delete(url, headers=self.headers, timeout=5)
        return response
