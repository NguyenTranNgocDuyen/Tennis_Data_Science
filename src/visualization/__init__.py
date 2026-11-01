"""Reusable, contract-aware charts for the historical tennis hand-off tables."""

from .contracts import load_contract, load_table, validate_table
from .export import export_figure
from .figures import (
    plot_ace_rate_by_surface,
    plot_duration_by_surface_format,
    plot_rank_group_win_rate,
    plot_season_matches,
    plot_surface_composition,
    plot_upset_rate_by_surface_format,
)
from .formatting import format_proportion

__all__ = [
    "export_figure", "format_proportion", "load_contract", "load_table", "validate_table",
    "plot_season_matches", "plot_surface_composition", "plot_duration_by_surface_format",
    "plot_upset_rate_by_surface_format", "plot_rank_group_win_rate", "plot_ace_rate_by_surface",
]
