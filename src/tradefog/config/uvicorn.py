"""Uvicorn server configuration."""

from inspect import signature
from typing import ClassVar, Self

import uvicorn
from pydantic import ConfigDict, model_validator

from tradefog.config.base import ConfigSection


class UvicornSettings(ConfigSection):
    """Pass validated arbitrary options through to Uvicorn."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="allow",
        frozen=True,
    )

    @model_validator(mode="after")
    def validate_option_names(self) -> Self:
        """Reject options unsupported by the installed Uvicorn version."""
        supported_options = set(signature(uvicorn.run).parameters)
        supported_options.remove("app")
        unknown_options = set(self.model_extra or {}) - supported_options
        if unknown_options:
            formatted_options = ", ".join(sorted(unknown_options))
            raise ValueError(
                f"Unknown Uvicorn option(s): {formatted_options}."
            )
        return self

    def options(self) -> dict[str, object]:
        """Return options while preserving Django logging by default."""
        options = self.model_dump()
        if "log_config" not in options:
            options["log_config"] = None
        return options
