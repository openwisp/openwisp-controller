import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class TestAsgiApplication(SimpleTestCase):
    def test_asgi_application_imports_without_django_setup(self):
        """Ensure ASGI_APPLICATION initializes Django before importing routes."""
        module_path, attr_name = settings.ASGI_APPLICATION.rsplit(".", 1)
        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = settings.SETTINGS_MODULE
        pythonpath = [p for p in sys.path if p]
        if existing := env.get("PYTHONPATH"):
            pythonpath.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)
        code = (
            f"import importlib; "
            f"mod = importlib.import_module({module_path!r}); "
            f"assert hasattr(mod, {attr_name!r})"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"Importing {settings.ASGI_APPLICATION} failed:\n{result.stderr}",
        )
