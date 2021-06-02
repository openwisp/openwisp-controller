from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from .. import commands


class TestCommandUtilities(TestCase):
    REBOOT_SCHEMA = {'title': 'Reboot', 'type': 'null'}

    def test_get_command_schema(self):
        with self.subTest('Test existing command option'):
            schema = commands.get_command_schema('reboot')
            self.assertEqual(schema, self.REBOOT_SCHEMA)

        with self.subTest('Test non-existing command option'):
            with self.assertRaises(ImproperlyConfigured):
                commands.get_command_schema('restart')

    def test_get_command_callable(self):
        with self.subTest('Test non-existing command option'):
            with self.assertRaises(ImproperlyConfigured):
                commands.get_command_callable('restart')

    def test_register_unregister_command(self):
        command = {
            'label': 'New Reboot Command',
            'schema': self.REBOOT_SCHEMA,
            'callable': None,
        }
        with self.subTest('Test registering command'):
            # Test command name is not instance of str
            with self.assertRaises(ImproperlyConfigured):
                commands.register_command([], command)

            # Test command config is not instance of dict
            with self.assertRaises(ImproperlyConfigured):
                commands.register_command('new_command', [])

            # Test expected use case for registering command
            commands.register_command('new_command', command)
            self.assertEqual(
                commands.get_command_schema('new_command'), self.REBOOT_SCHEMA
            )

        with self.subTest('Test re-registering same command'):
            with self.assertRaises(ImproperlyConfigured):
                commands.register_command('new_command', command)

        with self.subTest('Test unregistering command'):
            # Test command name is not instance of str
            with self.assertRaises(ImproperlyConfigured):
                commands.unregister_command([])
            commands.unregister_command('new_command')

        with self.subTest('Test re-unregistering command'):
            with self.assertRaises(ImproperlyConfigured):
                commands.unregister_command('new_command')

        with self.subTest('Test re-unregistering command choice'):
            with self.assertRaises(ImproperlyConfigured):
                commands._unregister_command_choice('new_command')
