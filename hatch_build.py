"""Build hooks for generated package resources."""

import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast, override

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.builders.wheel import WheelBuilderConfig

PACKAGE_ROOT = Path(__file__).parent / "src/tradefog"
sys.path.insert(0, str(PACKAGE_ROOT.parent))

from tradefog.assets.build import build_frontend_assets


class CustomBuildHook(BuildHookInterface[WheelBuilderConfig]):
    """Generate translations and frontend resources for wheels."""

    _temporary_directory: TemporaryDirectory[str] | None = None

    @override
    def initialize(
        self,
        version: str,
        build_data: dict[str, object],
    ) -> None:
        """Generate every tracked package resource for the wheel."""
        del version
        msgfmt = shutil.which("msgfmt")
        if msgfmt is None:
            raise RuntimeError(
                "GNU gettext is required to build tradefog translations."
            )

        locale_root = Path(self.root) / "src/tradefog/locale"
        temporary_directory = TemporaryDirectory(
            prefix="tradefog-translations-"
        )
        self._temporary_directory = temporary_directory
        output_root = Path(temporary_directory.name)

        force_include = cast(
            dict[str, str],
            build_data["force_include"],
        )

        static_output_root = output_root / "static"
        for output_path in build_frontend_assets(static_output_root):
            relative_path = output_path.relative_to(static_output_root)
            package_path = Path("tradefog/static") / relative_path
            force_include[str(output_path)] = package_path.as_posix()

        for source_path in locale_root.rglob("*.po"):
            relative_path = source_path.relative_to(locale_root).with_suffix(
                ".mo"
            )
            output_path = output_root / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            _ = subprocess.run(
                [msgfmt, "--check", "-o", output_path, source_path],
                check=True,
            )
            package_path = Path("tradefog/locale") / relative_path
            force_include[str(output_path)] = package_path.as_posix()

    @override
    def finalize(
        self,
        version: str,
        build_data: dict[str, object],
        artifact_path: str,
    ) -> None:
        """Remove temporary compiled catalogs after creating the wheel."""
        del version, build_data, artifact_path
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
