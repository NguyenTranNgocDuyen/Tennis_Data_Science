"""Explicit figure export with protection against accidental overwrite."""
from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure


def export_figure(figure: Figure, output_dir: Path, stem: str, *, overwrite: bool = False) -> tuple[Path, Path]:
    """Export a figure to PNG and SVG, refusing to overwrite by default."""
    directory = Path(output_dir)
    png, svg = directory / f"{stem}.png", directory / f"{stem}.svg"
    if not overwrite and any(path.exists() for path in (png, svg)):
        raise FileExistsError(f"Refusing to overwrite existing figure(s) for {stem!r}")
    directory.mkdir(parents=True, exist_ok=True)
    figure.savefig(png, bbox_inches="tight")
    figure.savefig(svg, bbox_inches="tight")
    return png, svg
