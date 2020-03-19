import io
import os
from contextlib import redirect_stdout

import mock
from django.conf import settings
from django.test import TestCase
from mockssh import Server

from .base import CreateConnectionsMixin


class TestSsh(CreateConnectionsMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mock_ssh_server = Server({'root': cls._TEST_RSA_PRIVATE_KEY_PATH}).__enter__()
        cls.ssh_server.port = cls.mock_ssh_server.port

    @classmethod
    def tearDownClass(cls):
        cls.mock_ssh_server.__exit__()

    def test_connection_connect(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            dc.connector_instance.exec_command('echo test')
        output = stdout.getvalue()
        self.assertIn('$:> echo test\ntest', output)

    def test_connection_failed_command(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(Exception):
                dc.connector_instance.exec_command('wrongcommand')
        output = stdout.getvalue()
        self.assertIn('/bin/sh: 1: wrongcommand: not found', output)
        self.assertIn('# Previus command failed, aborting...', output)

    @mock.patch('scp.SCPClient.putfo')
    def test_connection_upload(self, putfo_mocked):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connector_instance.connect()
        # needs a binary file to test all lines
        fl = open(os.path.join(settings.BASE_DIR, '../media/floorplan.jpg'), 'rb')
        dc.connector_instance.upload(fl, '/tmp/test')
        putfo_mocked.assert_called_once()
