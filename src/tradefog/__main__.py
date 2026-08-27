"""Command-line entry point for tradefog."""

import os
import sys

from django.core.management import execute_from_command_line


def main() -> None:
    """Run a tradefog management command."""
    _ = os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "tradefog.settings",
    )
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
