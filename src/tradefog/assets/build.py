"""Build generated frontend resources from their tracked sources."""

import copy
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = PACKAGE_ROOT / "assets"
STATIC_ROOT = PACKAGE_ROOT / "static"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def compile_styles(output_root: Path) -> Path:
    """Compile the application stylesheet into a static resource."""
    sass = shutil.which("sass")
    if sass is None:
        raise RuntimeError("Dart Sass is required to build tradefog styles.")

    source_path = ASSET_ROOT / "styles/tradefog.scss"
    output_path = output_root / "tradefog/css/tradefog.css"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = subprocess.run(
        [
            sass,
            "--style=compressed",
            "--no-source-map",
            source_path,
            output_path,
        ],
        check=True,
    )
    return output_path


def build_icon_sprite(output_root: Path) -> Path:
    """Build a deterministic SVG sprite from the selected Tabler icons."""
    ElementTree.register_namespace("", SVG_NAMESPACE)
    sprite = ElementTree.Element(f"{{{SVG_NAMESPACE}}}svg")
    icon_root = ASSET_ROOT / "icons/tabler"

    for source_path in sorted(icon_root.glob("*.svg")):
        source = ElementTree.parse(source_path).getroot()
        symbol_attributes = {
            "id": f"tabler-{source_path.stem}",
            "viewBox": source.attrib["viewBox"],
        }
        for attribute in (
            "fill",
            "stroke",
            "stroke-width",
            "stroke-linecap",
            "stroke-linejoin",
        ):
            if value := source.attrib.get(attribute):
                symbol_attributes[attribute] = value

        symbol = ElementTree.SubElement(
            sprite,
            f"{{{SVG_NAMESPACE}}}symbol",
            symbol_attributes,
        )
        for child in source:
            symbol.append(copy.deepcopy(child))

    ElementTree.indent(sprite, space="  ")
    output_path = output_root / "tradefog/icons/tabler.svg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = ElementTree.ElementTree(sprite).write(
        output_path,
        encoding="unicode",
        xml_declaration=False,
    )
    return output_path


def build_frontend_assets(output_root: Path) -> list[Path]:
    """Build all generated frontend resources into ``output_root``."""
    return [
        compile_styles(output_root),
        build_icon_sprite(output_root),
    ]


def main() -> None:
    """Build frontend resources into the package static directory."""
    _ = build_frontend_assets(STATIC_ROOT)


if __name__ == "__main__":
    main()
