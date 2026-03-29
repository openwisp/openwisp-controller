import fnmatch

from django.conf import settings
from django_minify_compress_staticfiles.storage import (
    MinicompressStorage as BaseMinicompressStorage,
)


class FileHashedNameMixin:
    default_excluded_patterns = ["leaflet/*/*.png"]
    excluded_patterns = default_excluded_patterns + getattr(
        settings, "OPENWISP_STATICFILES_VERSIONED_EXCLUDE", []
    )

    def hashed_name(self, name, content=None, filename=None):
        if not any(
            fnmatch.fnmatch(name, pattern) for pattern in self.excluded_patterns
        ):
            return super().hashed_name(name, content, filename)
        return name


class CompressStaticFilesStorage(
    FileHashedNameMixin,
    BaseMinicompressStorage,
):
    """Like MinicompressStorage, but allows excluding some files."""

    pass
