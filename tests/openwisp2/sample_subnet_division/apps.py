from openwisp_controller.subnet_division.apps import SubnetDivisionConfig


class SampleSubnetDivisionConfig(SubnetDivisionConfig):
    name = 'openwisp2.sample_subnet_division'
    label = 'sample_subnet_division'


del SubnetDivisionConfig
