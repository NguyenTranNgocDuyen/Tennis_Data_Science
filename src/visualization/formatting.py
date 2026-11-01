"""Presentation helpers shared by published charts."""
from __future__ import annotations

from matplotlib.ticker import PercentFormatter


def format_proportion(value: float, decimals: int = 1) -> str:
    """Format a 0–1 proportion as percent and reject an already-percent value."""
    if not 0 <= value <= 1:
        raise ValueError("Expected a proportion in [0, 1], not a percentage")
    return f"{value * 100:.{decimals}f}%"


def apply_tennis_theme() -> None:
    """Apply a small, portable visual theme without selecting a GUI backend."""
    from matplotlib import rcParams
    rcParams.update({"figure.dpi": 130, "savefig.dpi": 180, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "font.size": 10})


def percent_axis(ax) -> None:
    ax.yaxis.set_major_formatter(PercentFormatter(1))


def add_provenance_note(ax, source: str, denominator: str, limitation: str) -> None:
    """Place a compact source, denominator and limitation note below an axes."""
    ax.text(0, -0.27, f"Nguồn: {source}\nMẫu số: {denominator}\nGiới hạn: {limitation}",
            transform=ax.transAxes, va="top", ha="left", fontsize=8, color="#3d4852", wrap=True)
