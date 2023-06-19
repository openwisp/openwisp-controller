from openwisp_controller.config.apps import ConfigConfig


class SampleConfigConfig(ConfigConfig):
    name = 'openwisp2.sample_config'
    label = 'sample_config'


del ConfigConfig
