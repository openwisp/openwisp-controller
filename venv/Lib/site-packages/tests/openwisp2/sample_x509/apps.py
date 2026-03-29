from django_x509.apps import DjangoX509Config


class SampleX509Config(DjangoX509Config):
    name = "openwisp2.sample_x509"
    verbose_name = "sample_x509"


del DjangoX509Config
