from unittest.mock import patch

from django.db import transaction
from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.config.handlers import devicegroup_templates_change_handler

Device = load_model("config", "Device")
DeviceGroup = load_model("config", "DeviceGroup")
Config = load_model("config", "Config")


class ForceRollback(Exception):
    """Sentinel exception used to deliberately roll back a transaction in tests."""


class TestHandlersTransaction(TransactionTestCase):
    @patch("openwisp_controller.config.tasks.change_devices_templates.delay")
    def test_devicegroup_templates_change_handler_on_commit(self, mock_delay):
        """
        Test that change_devices_templates is called via delay and only after
        transaction.on_commit block commits successfully.
        """

        class MockMeta:
            def __init__(self, model_name):
                self.model_name = model_name

        class MockState:
            def __init__(self, adding):
                self.adding = adding

        class MockInstance:
            def __init__(self, id, model_name):
                self.id = id
                self._meta = MockMeta(model_name)
                self._state = MockState(adding=False)

        # Test cases for each model caller
        model_names = [
            Device._meta.model_name,
            DeviceGroup._meta.model_name,
            Config._meta.model_name,
        ]

        for model_name in model_names:
            with self.subTest(model_name=model_name):
                mock_instance = MockInstance(id="test-id", model_name=model_name)
                kwargs = {}
                if model_name == Config._meta.model_name:
                    kwargs["backend"] = "test-backend"
                    kwargs["old_backend"] = "old-backend"
                elif model_name == DeviceGroup._meta.model_name:
                    kwargs["templates"] = []
                    kwargs["old_templates"] = []
                elif model_name == Device._meta.model_name:
                    kwargs["group_id"] = "test-group"
                    kwargs["old_group_id"] = "old-group"

                # Case 1: Transaction commits
                mock_delay.reset_mock()
                with transaction.atomic():
                    devicegroup_templates_change_handler(mock_instance, **kwargs)
                    # Should not be called inside the transaction
                    mock_delay.assert_not_called()

                mock_delay.assert_called_once()  # Should be called after commit

                # Case 2: Transaction rolls back
                mock_delay.reset_mock()
                with self.assertRaises(ForceRollback):
                    with transaction.atomic():
                        devicegroup_templates_change_handler(mock_instance, **kwargs)
                        mock_delay.assert_not_called()
                        raise ForceRollback

                # Should not be called because it rolled back
                mock_delay.assert_not_called()

    @patch("openwisp_controller.config.tasks.change_devices_templates.delay")
    def test_devicegroup_templates_change_handler_list_branch(self, mock_delay):
        """
        Test that the list branch of devicegroup_templates_change_handler
        (type(instance) is list) correctly dispatches change_devices_templates.delay
        after commit and not on rollback.
        """
        instance_list = ["device-id-1", "device-id-2"]
        kwargs = {"group_id": "test-group", "old_group_id": "old-group"}

        with self.subTest("list branch: delay called after commit"):
            mock_delay.reset_mock()
            with transaction.atomic():
                devicegroup_templates_change_handler(instance_list, **kwargs)
                # Should not be called inside the transaction
                mock_delay.assert_not_called()

            mock_delay.assert_called_once()  # Should be called after commit

        with self.subTest("list branch: delay not called on rollback"):
            mock_delay.reset_mock()
            with self.assertRaises(ForceRollback):
                with transaction.atomic():
                    devicegroup_templates_change_handler(instance_list, **kwargs)
                    mock_delay.assert_not_called()
                    raise ForceRollback

            # Should not be called because it rolled back
            mock_delay.assert_not_called()
