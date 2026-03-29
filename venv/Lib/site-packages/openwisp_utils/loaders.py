import importlib
import os

from django.template.loaders.filesystem import Loader as FilesystemLoader

from .settings import EXTENDED_APPS


class DependencyLoader(FilesystemLoader):
    """Allows loading templates of apps listed in settings.EXTENDED_APPS.

    Looks in the "templates/"" directory of apps listed in
    settings.EXTENDED_APPS. Defaults to [].
    """

    dependencies = EXTENDED_APPS

    def get_dirs(self):
        dirs = []
        for dependency in self.dependencies:
            module = importlib.import_module(dependency)
            dirs.append("{0}/templates".format(os.path.dirname(module.__file__)))
        return dirs
