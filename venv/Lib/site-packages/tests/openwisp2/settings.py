import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = True

ALLOWED_HOSTS = []

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "djangox509.db"}
}

SECRET_KEY = "fn)t*+$)ugeyip6-#txyy$5wf2ervc0d2n#h)qb)y5@ly$t*@w"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django_x509",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "openwisp2.urls"

TIME_ZONE = "Europe/Rome"
LANGUAGE_CODE = "en-gb"
USE_TZ = True
USE_I18N = False
USE_L10N = False
STATIC_URL = "/static/"
CORS_ORIGIN_ALLOW_ALL = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
                "openwisp_utils.loaders.DependencyLoader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

if os.environ.get("SAMPLE_APP", False):
    INSTALLED_APPS.remove("django_x509")
    EXTENDED_APPS = ["django_x509"]
    INSTALLED_APPS.append("openwisp2.sample_x509")
    DJANGO_X509_CA_MODEL = "sample_x509.Ca"
    DJANGO_X509_CERT_MODEL = "sample_x509.Cert"

# local settings must be imported before test runner otherwise they'll be ignored
try:
    from local_settings import *  # noqa
except ImportError:
    pass
