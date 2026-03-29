from django.conf import settings


def get_setting(name, default=None):
    """Get setting with MINICOMPRESS_ prefix."""
    return getattr(settings, f"MINICOMPRESS_{name}", default)


DEFAULT_SETTINGS = {
    "ENABLED": True,
    "MINIFY_FILES": True,
    "BROTLI_COMPRESSION": True,
    "GZIP_COMPRESSION": True,
    "MIN_FILE_SIZE": 200,
    "MAX_FILE_SIZE": 10485760,
    "COMPRESSION_LEVEL_GZIP": 6,
    "COMPRESSION_LEVEL_BROTLI": 4,
    "PRESERVE_COMMENTS": True,
    "MAX_FILES_PER_RUN": 1000,
    "SUPPORTED_EXTENSIONS": {
        "css": True,
        "js": True,
        "txt": True,
        "xml": True,
        "json": True,
        "svg": True,
        "md": True,
        "rst": True,
        "html": True,
        "htm": True,
    },
    "EXCLUDE_PATTERNS": [
        "*.min.*",
        "*-min.*",
        "*.gz",
        "*.br",
        "*.zip",
    ],
}
