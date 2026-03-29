# For backward compatibility and shorthand
from .utils import (  # noqa
    AdminActionPermTestMixin,
    AssertNumQueriesSubTestMixin,
    CaptureOutput,
    TimeLoggingTestResult,
    TimeLoggingTestRunner,
    capture_any_output,
    capture_stderr,
    capture_stdout,
    catch_signal,
)

try:
    from .selenium import SeleniumTestMixin  # noqa
except ImportError:
    # Selenium is an optional dependency.
    # Skip import errors since not all modules use browser-based tests.
    pass
