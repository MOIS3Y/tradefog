"""Uvicorn server configuration."""

from tradefog.config.base import ConfigSection


class UvicornSettings(ConfigSection):
    """Uvicorn server execution parameters."""

    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    workers: int = 1
