"""Reproducible descriptive statistics with explicit analysis populations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.preprocessing import player_matches


TABLE_NOTES = {
    "duration_review": "All retained matches flagged minutes <20 or >360; includes short retirements. A review flag is not proof of error and does not delete the record.",
    "season_summary": "All retained records by source season; completion count, duration coverage and ranked completed-match upset denominator. Rates are proportions 0–1.",
    "surface_summary": "All retained records by surface; duration uses only completed records with known positive minutes; upset uses completed records with two known unequal ranks.",
    "season_surface": "All retained records grouped by source season and surface; same metric definitions as surface_summary.",
    "duration_by_surface_format": "Completed matches grouped by surface and best_of. n_duration is the nonmissing duration denominator; quantiles use pandas linear interpolation. Review flags retained.",
    "duration_sensitivity": "Completed matches by surface and best_of, removing minutes outside [20,360] only in this sensitivity table.",
    "upsets_by_surface_format": "Completed matches with known unequal ranks, grouped by surface and best_of. Upset = winner_rank > loser_rank. No missing rank imputation.",
    "rank_group_performance": "Completed player-match appearances including both winner and loser. A match contributes twice; group membership uses pre-event ranking. Unknown retained as own group.",
    "player_summary": "Completed appearances by stable player_id. Name is last observed by season and input order, not an identifier. No inference about intrinsic skill.",
    "serve_by_surface": "Completed player-match appearances. Each metric uses paired nonmissing numerator and strictly positive denominator. Rate = sum(numerator)/sum(denominator), not mean of per-match rates. n_appearances and denominator are metric-specific.",
    "missingness_by_season": "All retained matches; missing values after cleaning, long form by season and original source field.",
    "numeric_summary": "All retained records, numeric descriptive statistics; ranks/ages count winner and loser columns separately. Durations here include unfinished matches; use duration tables for completed-only comparison.",
    "score_status": "All retained records grouped by parsed score status; completed means recognized score syntax without RET W/O DEF ABN markers.",
    "quality_by_field": "Raw versus retained cleaned missingness. Denominators differ because of scope filtering; these rates alone do not isolate the effect of cleaning."
}


def summary(d: pd.DataFrame) -> dict:
    complete = d.loc[d.is_completed]
    ranked = complete.loc[complete.rank_pair_available]
    duration = complete.minutes.dropna()
    return {"n_matches": len(d), "n_completed": len(complete),
            "n_tournaments": d.tourney_id.nunique(), "n_duration": len(duration),
            "median_minutes": duration.median() if len(duration) else np.nan,
            "n_ranked_completed": len(ranked), "n_upsets": int(ranked.is_upset.sum()),
            "upset_rate": float(ranked.is_upset.mean()) if len(ranked) else np.nan}


def grouped_summary(d: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    columns = keys + list(summary(d).keys())
    rows = []
    for key, g in d.groupby(keys, observed=True, dropna=False, sort=True):
        if not isinstance(key, tuple):
            key = (key,)
        rows.append({**dict(zip(keys, key)), **summary(g)})
    return pd.DataFrame(rows, columns=columns)


def duration_table(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (surface, best_of), g in d.groupby(["surface_group", "best_of"], observed=True, sort=True):
        v = g.minutes.dropna().astype(float)
        rows.append({"surface_group":surface, "best_of":best_of, "n_matches":len(g),
                     "n_duration":len(v), "missing_duration":int(g.minutes.isna().sum()),
                     "mean_minutes":v.mean(), "std_minutes":v.std(), "p25_minutes":v.quantile(.25),
                     "median_minutes":v.median(), "p75_minutes":v.quantile(.75),
                     "p95_minutes":v.quantile(.95), "max_minutes":v.max()})
    return pd.DataFrame(rows, columns=["surface_group","best_of","n_matches","n_duration","missing_duration",
                                      "mean_minutes","std_minutes","p25_minutes","median_minutes","p75_minutes","p95_minutes","max_minutes"])


def build_tables(matches: pd.DataFrame, raw: pd.DataFrame, schema: dict) -> dict[str, pd.DataFrame]:
    m = matches
    completed = m.loc[m.is_completed]
    players = player_matches(m)
    p = players.loc[players.is_completed].copy()
    tables = {"season_summary":grouped_summary(m, ["season"]),
              "duration_review":m.loc[m.duration_review_flag,["match_id","source_file","source_row","tourney_name","winner_name","loser_name","score","score_status","best_of","minutes"]].reset_index(drop=True),
              "surface_summary":grouped_summary(m, ["surface_group"]),
              "season_surface":grouped_summary(m, ["season", "surface_group"]),
              "duration_by_surface_format":duration_table(completed),
              "duration_sensitivity":duration_table(completed.loc[~completed.duration_review_flag]),
              "upsets_by_surface_format":grouped_summary(completed.loc[completed.rank_pair_available], ["surface_group", "best_of"])}
    rank = p.groupby("rank_group", observed=True).agg(n_appearances=("won","size"), wins=("won","sum"), n_players=("player_id","nunique")).reset_index()
    rank["losses"] = rank.n_appearances - rank.wins
    rank["win_rate"] = rank.wins / rank.n_appearances
    tables["rank_group_performance"] = rank
    by_player = p.groupby("player_id", observed=True).agg(player_name=("player_name","last"), n_appearances=("won","size"), wins=("won","sum")).reset_index()
    by_player["losses"] = by_player.n_appearances - by_player.wins
    by_player["win_rate"] = by_player.wins / by_player.n_appearances
    tables["player_summary"] = by_player.sort_values(["wins","player_id"], ascending=[False,True]).reset_index(drop=True)
    serve_rows = []
    for surface, g in p.groupby("surface_group", observed=True):
        specs = [("ace_rate","ace",g.svpt), ("double_fault_rate","df",g.svpt),
                 ("first_serve_in_rate","1stIn",g.svpt), ("first_serve_win_rate","1stWon",g["1stIn"]),
                 ("second_serve_win_rate","2ndWon",g.svpt-g["1stIn"]),
                 ("break_point_save_rate","bpSaved",g.bpFaced)]
        for metric, numerator_col, den in specs:
            num = g[numerator_col]
            valid = num.notna() & den.notna() & den.gt(0)
            a, b = num.loc[valid].sum(), den.loc[valid].sum()
            serve_rows.append({"surface_group":surface, "metric":metric, "n_appearances":int(valid.sum()),
                               "n_possible_appearances":len(g), "numerator":int(a), "denominator":int(b),
                               "rate":float(a/b) if b else np.nan})
    tables["serve_by_surface"] = pd.DataFrame(serve_rows, columns=["surface_group","metric","n_appearances","n_possible_appearances","numerator","denominator","rate"])
    original = list(schema["properties"])
    missing_rows = []
    for season, g in m.groupby("season", observed=True):
        for col in original:
            missing_rows.append({"season":season, "field":col, "n_rows":len(g),
                                 "n_missing":int(g[col].isna().sum()), "missing_rate":float(g[col].isna().mean())})
    tables["missingness_by_season"] = pd.DataFrame(missing_rows)
    numerical = [c for c in original if schema["properties"][c]["x-csv"]["dtype"] in {"integer", "number"} and c not in {"winner_id","loser_id","source_row","source_season","match_num"}]
    numeric = m[numerical].astype(float).describe(percentiles=[.25,.5,.75,.95]).T.rename_axis("field").reset_index()
    tables["numeric_summary"] = numeric.rename(columns={"25%":"p25", "50%":"median", "75%":"p75", "95%":"p95"})
    status = m.groupby("score_status", observed=True).size().reset_index(name="n_matches")
    status["share"] = status.n_matches / len(m) if len(m) else np.nan
    tables["score_status"] = status
    quality = []
    for col in original:
        before = raw[col].astype("string").str.strip().replace("",pd.NA)
        quality.append({"field":col, "raw_n_rows":len(raw), "raw_missing":int(before.isna().sum()),
                        "raw_missing_rate":float(before.isna().mean()), "clean_n_rows":len(m),
                        "clean_missing":int(m[col].isna().sum()), "clean_missing_rate":float(m[col].isna().mean())})
    tables["quality_by_field"] = pd.DataFrame(quality)
    verify_tables(m, tables)
    return tables


def verify_tables(m: pd.DataFrame, tables: dict[str,pd.DataFrame]) -> None:
    """Accounting checks independent of group presentation or report wording."""
    n_complete = int(m.is_completed.sum())
    assert int(tables["season_summary"].n_matches.sum()) == len(m)
    assert int(tables["surface_summary"].n_matches.sum()) == len(m)
    assert int(tables["score_status"].n_matches.sum()) == len(m)
    for name in ("rank_group_performance", "player_summary"):
        t = tables[name]
        assert int(t.n_appearances.sum()) == 2*n_complete
        assert int(t.wins.sum()) == n_complete
        assert (t.wins + t.losses).eq(t.n_appearances).all()
    ranked = m.loc[m.is_completed & m.rank_pair_available]
    t = tables["upsets_by_surface_format"]
    assert int(t.n_matches.sum()) == len(ranked)
    assert int(t.n_upsets.sum()) == int(ranked.is_upset.sum())
    for t in tables.values():
        for col in t.columns:
            if col.endswith("_rate") or col in {"rate", "share"}:
                assert t[col].dropna().between(0,1).all(), col
