from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pandas as pd
import pytest

from src.visualization import export_figure, format_proportion, load_contract, load_table, validate_table
from src.visualization import plot_ace_rate_by_surface, plot_duration_by_surface_format, plot_rank_group_win_rate
from src.visualization import plot_season_matches, plot_surface_composition, plot_upset_rate_by_surface_format

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "reports" / "tables"
CONTRACT = TABLES / "table_contract.json"


@pytest.fixture
def contract():
    return load_contract(CONTRACT)


@pytest.mark.parametrize("value, expected", [(0, "0.0%"), (0.054, "5.4%"), (0.978, "97.8%"), (1, "100.0%")])
def test_format_proportion(value, expected):
    assert format_proportion(value) == expected


def test_format_proportion_rejects_already_percent_value():
    with pytest.raises(ValueError, match="proportion"):
        format_proportion(5.4)


def test_contract_rejects_missing_column(contract):
    with pytest.raises(ValueError, match="missing required columns"):
        validate_table(pd.DataFrame({"season": [2020]}), "season_summary", contract)


def test_contract_rejects_percentage_stored_as_proportion(contract):
    frame = load_table("surface_summary", TABLES, CONTRACT)
    frame.loc[0, "upset_rate"] = 35.0
    with pytest.raises(ValueError, match="\\[0, 1\\]"):
        validate_table(frame, "surface_summary", contract)


@pytest.mark.parametrize("table_name, plotter", [
    ("season_summary", plot_season_matches), ("surface_summary", plot_surface_composition),
    ("duration_by_surface_format", plot_duration_by_surface_format),
    ("upsets_by_surface_format", plot_upset_rate_by_surface_format),
    ("rank_group_performance", plot_rank_group_win_rate), ("serve_by_surface", plot_ace_rate_by_surface),
])
def test_figures_are_headless_and_do_not_mutate_input(table_name, plotter):
    frame = load_table(table_name, TABLES, CONTRACT)
    original = frame.copy(deep=True)
    figure = plotter(frame)
    assert figure.axes and figure.axes[0].get_title()
    pd.testing.assert_frame_equal(frame, original)


def test_figures_include_required_denominator_annotations():
    cases = [("duration_by_surface_format", plot_duration_by_surface_format, "n_duration"),
             ("upsets_by_surface_format", plot_upset_rate_by_surface_format, "n_ranked_completed"),
             ("rank_group_performance", plot_rank_group_win_rate, "n_appearances"),
             ("serve_by_surface", plot_ace_rate_by_surface, "numerator/denominator")]
    for table_name, plotter, expected in cases:
        figure = plotter(load_table(table_name, TABLES, CONTRACT))
        assert expected in " ".join(text.get_text() for text in figure.axes[0].texts)


def test_export_creates_png_and_svg_without_silent_overwrite(tmp_path):
    figure = plot_season_matches(load_table("season_summary", TABLES, CONTRACT))
    png, svg = export_figure(figure, tmp_path, "season_matches")
    assert png.exists() and png.stat().st_size > 0 and svg.exists() and svg.stat().st_size > 0
    with pytest.raises(FileExistsError):
        export_figure(figure, tmp_path, "season_matches")
