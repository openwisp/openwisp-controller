from openwisp_controller.connection.tests.pytest import (
    TestBatchCommandConsumer as BaseTestBatchCommandConsumer,
)
from openwisp_controller.connection.tests.pytest import (
    TestCommandsConsumer as BaseTestCommandsConsumer,
)


class TestCommandsConsumer(BaseTestCommandsConsumer):
    pass


class TestBatchCommandConsumer(BaseTestBatchCommandConsumer):
    app_label = "sample_connection"


del BaseTestBatchCommandConsumer
del BaseTestCommandsConsumer
