from openwisp_controller.pki.apps import PkiConfig


class SamplePkiConfig(PkiConfig):
    name = 'openwisp2.sample_pki'
    label = 'sample_pki'


del PkiConfig
