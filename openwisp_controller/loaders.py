import os

from django.template.loaders.filesystem import Loader as FilesystemLoader

from . import __dependencies__


class DependencyLoader(FilesystemLoader):
    """
    A template loeader that looks in templates dir of
    django-apps listed in openwisp_controller.__dependencies__
    """
    dependencies = __dependencies__

    def get_dirs(self):
        dirs = []
        for dependency in self.dependencies:
            module = __import__(dependency)
            dirs.append('{0}/templates'.format(os.path.dirname(module.__file__)))
        return dirs
