import collections
import importlib
import os

from django.contrib.staticfiles.finders import FileSystemFinder
from django.core.files.storage import FileSystemStorage

from .settings import EXTENDED_APPS


class DependencyFinder(FileSystemFinder):
    """Finds static files of apps listed in settings.EXTENDED_APPS."""

    dependencies = list(EXTENDED_APPS) + ["openwisp_utils"]

    def __init__(self, app_names=None, *args, **kwargs):
        self.locations = []
        self.storages = collections.OrderedDict()
        for dependency in self.dependencies:
            module = importlib.import_module(dependency)
            path = f"{os.path.dirname(module.__file__)}/static"
            if os.path.isdir(path):
                self.locations.append(("", path))
        for prefix, root in self.locations:
            filesystem_storage = FileSystemStorage(location=root)
            filesystem_storage.prefix = prefix
            self.storages[root] = filesystem_storage
