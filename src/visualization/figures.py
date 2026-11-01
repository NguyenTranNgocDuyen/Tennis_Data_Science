"""Six publication charts built only from stable analysis hand-off tables."""
from __future__ import annotations

import pandas as pd
from matplotlib.figure import Figure

from .formatting import add_provenance_note, apply_tennis_theme, format_proportion, percent_axis

COLORS = {"Hard": "#2c6e8f", "Clay": "#bb7445", "Grass": "#5e8b4a", "2020": "#c9473d"}


def _figure(size: tuple[float, float] = (8, 4.8)) -> tuple[Figure, object]:
    import matplotlib.pyplot as plt
    apply_tennis_theme()
    return plt.subplots(figsize=size, layout="constrained")


def _surface_color(values: pd.Series) -> list[str]:
    return [COLORS.get(str(value), "#6b7280") for value in values]


def plot_season_matches(frame: pd.DataFrame) -> Figure:
    """Show retained match counts by source season and highlight 2020."""
    data = frame.loc[:, ["season", "n_matches"]].copy().sort_values("season")
    fig, ax = _figure()
    colors = [COLORS["2020"] if year == 2020 else COLORS["Hard"] for year in data["season"]]
    bars = ax.bar(data["season"].astype(str), data["n_matches"], color=colors)
    ax.bar_label(bars, padding=3, fmt="%d", fontsize=8)
    ax.set(title="Số trận được giữ lại theo mùa nguồn", xlabel="Mùa nguồn", ylabel="Số trận")
    add_provenance_note(ax, "reports/tables/season_summary.csv", "n_matches: mọi bản ghi được giữ lại theo season",
                        "2020 thấp hơn mô tả số bản ghi trong nguồn, không chứng minh nguyên nhân.")
    return fig


def plot_surface_composition(frame: pd.DataFrame) -> Figure:
    """Show the composition of all retained records by surface."""
    data = frame.loc[:, ["surface_group", "n_matches"]].copy()
    order = [surface for surface in ["Hard", "Clay", "Grass"] if surface in set(data.surface_group)]
    data = data.set_index("surface_group").loc[order].reset_index()
    fig, ax = _figure()
    bars = ax.bar(data.surface_group, data.n_matches, color=_surface_color(data.surface_group))
    total = data.n_matches.sum()
    ax.bar_label(bars, labels=[f"{value / total:.1%}" for value in data.n_matches], padding=3)
    ax.set(title="Cơ cấu mặt sân của bản ghi được giữ lại", xlabel="Mặt sân", ylabel="Số trận")
    add_provenance_note(ax, "reports/tables/surface_summary.csv", "n_matches: mọi bản ghi được giữ lại",
                        "Cơ cấu không chỉ giới hạn trận completed.")
    return fig


def plot_duration_by_surface_format(frame: pd.DataFrame) -> Figure:
    """Compare median completed-match duration within each best-of format."""
    data = frame.loc[:, ["surface_group", "best_of", "median_minutes", "n_duration"]].copy()
    surfaces = [surface for surface in ["Hard", "Clay", "Grass"] if surface in set(data.surface_group)]
    formats = sorted(data.best_of.dropna().unique())
    fig, ax = _figure((8.5, 5.1))
    import numpy as np
    x = np.arange(len(surfaces)); width = 0.72 / max(len(formats), 1)
    for index, best_of in enumerate(formats):
        values = data.loc[data.best_of.eq(best_of)].set_index("surface_group").reindex(surfaces)
        bars = ax.bar(x - 0.36 + width / 2 + index * width, values.median_minutes, width,
                      label=f"Best of {best_of}", color="#2c6e8f" if best_of == 3 else "#bb7445")
        ax.bar_label(bars, labels=[f"n={int(n):,}" for n in values.n_duration], padding=3, fontsize=8)
    ax.set_xticks(x, surfaces)
    ax.set(title="Median thời lượng theo mặt sân và thể thức", xlabel="Mặt sân", ylabel="Phút")
    ax.legend(title="Thể thức")
    add_provenance_note(ax, "reports/tables/duration_by_surface_format.csv", "n_duration: trận completed có minutes dương",
                        "Không gộp best-of; outlier 987/1.146 phút được giữ để review.")
    return fig


def plot_upset_rate_by_surface_format(frame: pd.DataFrame) -> Figure:
    """Show upset proportions for completed matches with comparable ranks."""
    data = frame.loc[:, ["surface_group", "best_of", "upset_rate", "n_ranked_completed"]].copy()
    surfaces = [surface for surface in ["Hard", "Clay", "Grass"] if surface in set(data.surface_group)]
    formats = sorted(data.best_of.dropna().unique())
    fig, ax = _figure((8.5, 5.1))
    import numpy as np
    x = np.arange(len(surfaces)); width = 0.72 / max(len(formats), 1)
    for index, best_of in enumerate(formats):
        values = data.loc[data.best_of.eq(best_of)].set_index("surface_group").reindex(surfaces)
        bars = ax.bar(x - 0.36 + width / 2 + index * width, values.upset_rate, width,
                      label=f"Best of {best_of}", color="#2c6e8f" if best_of == 3 else "#bb7445")
        ax.bar_label(bars, labels=[f"n={int(n):,}" for n in values.n_ranked_completed], padding=3, fontsize=8)
    ax.set_xticks(x, surfaces)
    ax.set(title="Tỷ lệ upset theo mặt sân và thể thức", xlabel="Mặt sân", ylabel="Tỷ lệ upset", ylim=(0, 0.5))
    percent_axis(ax); ax.legend(title="Thể thức")
    add_provenance_note(ax, "reports/tables/upsets_by_surface_format.csv", "n_ranked_completed: completed có hai rank khác nhau",
                        "Upset = winner_rank > loser_rank; đây là liên hệ mô tả.")
    return fig


def plot_rank_group_win_rate(frame: pd.DataFrame) -> Figure:
    """Show completed player-appearance win rates by pre-event rank group."""
    order = ["Top 10", "11–50", "51–100", "101+", "Unknown"]
    data = frame.loc[:, ["rank_group", "win_rate", "n_appearances"]].copy().set_index("rank_group").reindex(order).dropna().reset_index()
    fig, ax = _figure()
    bars = ax.bar(data.rank_group, data.win_rate, color="#2c6e8f")
    ax.bar_label(bars, labels=[f"{format_proportion(rate)}\nn={int(n):,}" for rate, n in zip(data.win_rate, data.n_appearances)], padding=3, fontsize=8)
    ax.set(title="Tỷ lệ thắng theo nhóm rank trước giải", xlabel="Nhóm rank", ylabel="Tỷ lệ thắng", ylim=(0, 0.9))
    percent_axis(ax)
    add_provenance_note(ax, "reports/tables/rank_group_performance.csv", "n_appearances: lượt người chơi ở trận completed",
                        "Mỗi trận đóng góp hai lượt; không suy ra năng lực nội tại của người chơi.")
    return fig


def plot_ace_rate_by_surface(frame: pd.DataFrame) -> Figure:
    """Show pooled ace rates, preserving the metric-specific serve denominator."""
    data = frame.loc[frame.metric.eq("ace_rate"), ["surface_group", "rate", "numerator", "denominator", "n_appearances"]].copy()
    order = [surface for surface in ["Hard", "Clay", "Grass"] if surface in set(data.surface_group)]
    data = data.set_index("surface_group").loc[order].reset_index()
    fig, ax = _figure((8.5, 5.1))
    bars = ax.bar(data.surface_group, data.rate, color=_surface_color(data.surface_group))
    labels = [f"{format_proportion(rate)}\n{int(num):,}/{int(den):,}" for rate, num, den in zip(data.rate, data.numerator, data.denominator)]
    ax.bar_label(bars, labels=labels, padding=3, fontsize=8)
    ax.set(title="Tỷ lệ ace gộp theo mặt sân", xlabel="Mặt sân", ylabel="Ace / điểm giao bóng", ylim=(0, max(data.rate) * 1.35))
    percent_axis(ax)
    add_provenance_note(ax, "reports/tables/serve_by_surface.csv (metric=ace_rate)", "numerator/denominator theo metric; n_appearances riêng",
                        "Tỷ lệ gộp, không phải trung bình tỷ lệ từng trận; stats thiếu không được điền.")
    return fig
