"""Export the six approved historical-table charts for member C."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.visualization import (  # noqa: E402
    export_figure, load_table, plot_ace_rate_by_surface, plot_duration_by_surface_format,
    plot_rank_group_win_rate, plot_season_matches, plot_surface_composition,
    plot_upset_rate_by_surface_format,
)


def main() -> None:
    tables_dir = ROOT / 'reports' / 'tables'
    contract_path = tables_dir / 'table_contract.json'
    figures_dir = ROOT / 'reports' / 'figures'
    specs = [
        ('season_matches', 'season_summary', plot_season_matches),
        ('surface_composition', 'surface_summary', plot_surface_composition),
        ('duration_surface_format', 'duration_by_surface_format', plot_duration_by_surface_format),
        ('upset_surface_format', 'upsets_by_surface_format', plot_upset_rate_by_surface_format),
        ('rank_group_win_rate', 'rank_group_performance', plot_rank_group_win_rate),
        ('ace_rate_surface', 'serve_by_surface', plot_ace_rate_by_surface),
    ]
    for stem, table_name, plotter in specs:
        figure = plotter(load_table(table_name, tables_dir, contract_path))
        png, svg = export_figure(figure, figures_dir, stem, overwrite=True)
        print(f'{png.relative_to(ROOT)} | {svg.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
