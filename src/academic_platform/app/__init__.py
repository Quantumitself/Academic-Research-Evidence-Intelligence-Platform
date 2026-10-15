"""Application bootstrap, configuration, and cross-cutting services.

This subpackage contains the entry-point bootstrapping logic, the runtime
directory resolver, the logging configuration, and the persistent
application configuration service. It must not import from
``academic_platform.ui`` at module scope.
"""

from academic_platform.app.configuration import (
    APP_CONFIG_FILENAME,
    APP_DIRECTORY_NAME,
    ENV_HOME,
    AppDirectories,
    ConfigurationError,
    load_runtime_directories,
)

__all__ = [
    "APP_CONFIG_FILENAME",
    "APP_DIRECTORY_NAME",
    "ENV_HOME",
    "AppDirectories",
    "ConfigurationError",
    "load_runtime_directories",
]