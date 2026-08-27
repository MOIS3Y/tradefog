"""Application logging formatters."""

from logging import Formatter
from time import gmtime
from typing import final


@final
class UtcFormatter(Formatter):
    """Format log timestamps consistently in UTC."""

    converter = gmtime
