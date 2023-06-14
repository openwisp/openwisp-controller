from openwisp_controller.connection.apps import ConnectionConfig


class SampleConnectionConfig(ConnectionConfig):
    name = 'openwisp2.sample_connection'
    label = 'sample_connection'


del ConnectionConfig
