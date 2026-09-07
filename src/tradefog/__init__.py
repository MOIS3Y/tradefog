"""Personal journal for a rules-based trading process."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tradefog")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = ["__version__"]
