import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_users.tests.test_api import AuthenticationMixin

from ..api.views import CommandPaginator
from .utils import CreateConnectionsMixin

Command = load_model('connection', 'Command')
command_qs = Command.objects.order_by('-created')


class TestCommandsAPI(TestCase, AuthenticationMixin, CreateConnectionsMixin):
    url_namespace = 'connection'

    def setUp(self):
        self.admin = self._get_admin()
        self.client.force_login(self.admin)
        self.device_conn = self._create_device_connection()
        self.device_id = self.device_conn.device.id

    def _create_command(self, device_conn=None):
        if not device_conn:
            device_conn = self.device_conn
        return Command.objects.create(
            device=device_conn.device,
            connection=device_conn,
            type='custom',
            input={'command': 'echo test'},
        )

    def _get_path(self, url_name, *args, **kwargs):
        path = reverse(f'{self.url_namespace}:{url_name}', args=args)
        if not kwargs:
            return path
        query_params = []
        for key, value in kwargs.items():
            query_params.append(f'{key}={value}')
        query_string = '&'.join(query_params)
        return f'{path}?{query_string}'

    @patch.object(CommandPaginator, 'page_size', 3)
    def test_command_list_api(self):
        number_of_commands = 6
        url = self._get_path('api_device_command_list_create', self.device_id)
        for _ in range(number_of_commands):
            self._create_command()
        self.assertEqual(command_qs.count(), number_of_commands)

        response = self.client.get(url)

        with self.subTest('Test "page" query in object notification list view'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], number_of_commands)
            self.assertIn(
                self._get_path(
                    'api_device_command_list_create', self.device_id, page=2
                ),
                response.data['next'],
            )
            self.assertEqual(response.data['previous'], None)
            self.assertEqual(len(response.data['results']), 3)

            next_response = self.client.get(response.data['next'])
            self.assertEqual(next_response.status_code, 200)
            self.assertEqual(next_response.data['count'], number_of_commands)
            self.assertEqual(
                next_response.data['next'], None,
            )
            self.assertIn(
                self._get_path('api_device_command_list_create', self.device_id),
                next_response.data['previous'],
            )
            self.assertEqual(len(next_response.data['results']), 3)

        with self.subTest('Test "page_size" query'):
            page_size = 3
            url = f'{url}?page_size={page_size}'
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], number_of_commands)
            self.assertIn(
                self._get_path(
                    'api_device_command_list_create',
                    self.device_id,
                    page=2,
                    page_size=page_size,
                ),
                response.data['next'],
            )
            self.assertEqual(response.data['previous'], None)
            self.assertEqual(len(response.data['results']), page_size)

            next_response = self.client.get(response.data['next'])
            self.assertEqual(next_response.status_code, 200)
            self.assertEqual(next_response.data['count'], number_of_commands)
            self.assertEqual(next_response.data['next'], None)
            self.assertIn(
                self._get_path(
                    'api_device_command_list_create',
                    self.device_id,
                    page_size=page_size,
                ),
                next_response.data['previous'],
            )
            self.assertEqual(len(next_response.data['results']), page_size)

        with self.subTest('Test individual result object'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            command_obj = response.data['results'][0]
            self.assertIn('id', command_obj)
            self.assertIn('status', command_obj)
            self.assertIn('type', command_obj)
            self.assertIn('input', command_obj)
            self.assertIn('output', command_obj)
            self.assertIn('device', command_obj)
            self.assertIn('connection', command_obj)

    def test_command_create_api(self):
        def test_command_attributes(self, payload):
            self.assertEqual(command_qs.count(), 1)
            command_obj = command_qs.first()
            self.assertEqual(command_obj.device_id, self.device_id)
            self.assertEqual(command_obj.type, payload['type'])
            self.assertEqual(command_obj.input, payload['input'])
            command_qs.delete()

        url = self._get_path('api_device_command_list_create', self.device_id)

        with self.subTest('Test "reboot" command'):
            payload = {
                'type': 'reboot',
                'input': None,
            }
            response = self.client.post(
                url, data=payload, content_type='application/json',
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

        with self.subTest('Test "reset_password" command'):
            payload = {
                'type': 'change_password',
                'input': {'password': 'ass@1234', 'confirm_password': 'Pass@1234'},
            }
            response = self.client.post(
                url, data=json.dumps(payload), content_type='application/json',
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

        with self.subTest('Test "custom" command'):
            payload = {
                'type': 'custom',
                'input': {'command': 'echo test'},
            }
            response = self.client.post(
                url, data=json.dumps(payload), content_type='application/json',
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

    def test_command_details_api(self):
        command_obj = self._create_command()
        url = self._get_path(
            'api_device_command_details', self.device_id, command_obj.id
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], str(command_obj.id))
        self.assertEqual(response.data['status'], command_obj.status)
        self.assertEqual(response.data['input'], command_obj.input_data)
        self.assertEqual(response.data['output'], command_obj.output)
        self.assertEqual(response.data['device'], str(command_obj.device_id))
        self.assertEqual(response.data['connection'], str(command_obj.connection_id))
        # These are hard coded because API reverts more verbose response
        self.assertEqual(response.data['type'], 'Custom commands')

    def test_bearer_authentication(self):
        self.client.logout()
        command_obj = self._create_command()
        token = self._obtain_auth_token(username='admin', password='tester')

        with self.subTest('Test creating command'):
            url = self._get_path('api_device_command_list_create', self.device_id)
            payload = {
                'type': 'custom',
                'input': {'command': 'echo test'},
            }
            response = self.client.post(
                url,
                data=payload,
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn('id', response.data)

        with self.subTest('Test retrieving command'):
            url = self._get_path(
                'api_device_command_details', self.device_id, command_obj.id
            )
            response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {token}',)
            self.assertEqual(response.status_code, 200)
            self.assertIn('id', response.data)

        with self.subTest('Test listing command'):
            url = self._get_path('api_device_command_list_create', self.device_id)
            response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {token}',)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 2)
