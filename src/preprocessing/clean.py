"""Deterministic cleaning, quarantine and feature engineering without imputation."""
from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pandas as pd

from src.data_validation import validate_frame

SERVE = ["ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced"]


@dataclass
class CleanResult:
    matches: pd.DataFrame
    excluded: pd.DataFrame
    quarantine: pd.DataFrame
    duplicates: pd.DataFrame
    issues: pd.DataFrame
    actions: pd.DataFrame
    flow: dict


def score_status(score) -> str:
    if pd.isna(score) or not str(score).strip():
        return "unknown"
    s = str(score).strip().upper()
    for marker, label in [(r"W\s*/\s*O|WALKOVER", "walkover"), (r"\bRET\b", "retired"),
                          (r"\bDEF\b|\bDEFAULT", "defaulted"), (r"\bABN\b|\bABD\b|CANCEL", "abandoned")]:
        if re.search(marker, s):
            return label
    # Syntactic score recognition, not a reconstruction of tennis scoring rules.
    token = r"(?:\d+-\d+(?:\(\d+\))?|\[\d+-\d+\])"
    return "completed" if re.fullmatch(rf"{token}(?:\s+{token})+", s) else "unknown"


def rank_group(rank: pd.Series) -> pd.Series:
    return pd.cut(rank, bins=[0, 10, 50, 100, np.inf], labels=["Top 10", "11–50", "51–100", "101+"]).astype("string").fillna("Unknown")


def clean_matches(raw: pd.DataFrame, schema: dict, config: dict) -> CleanResult:
    d = raw.copy().reset_index(drop=True)
    for col in d:
        d[col] = d[col].astype("string").str.strip().replace("", pd.NA)
    issues = validate_frame(d, schema)
    actions = []

    def log(indices, action, detail, field="*"):
        for idx in indices:
            actions.append({"row_index": int(idx), "source_file": d.at[idx, "source_file"],
                            "source_row": d.at[idx, "source_row"], "action": action,
                            "field": field, "detail": detail})

    scope = d.tourney_level.isin(config["included_levels"])
    for pattern in config["excluded_tournament_patterns"]:
        scope &= ~d.tourney_name.str.contains(pattern, regex=True, na=False)
    excluded = d.loc[~scope].copy()
    excluded["exclusion_reason"] = "outside_selected_levels_or_named_event_scope"
    log(excluded.index, "exclude_scope", "Outside ATP conventional singles scope")
    # Core errors take precedence over duplicate resolution within selected scope.
    bad_core = set(issues.loc[issues.severity.eq("error"), "row_index"]) & set(d.index[scope])
    quarantine = d.loc[sorted(bad_core)].copy()
    quarantine["quarantine_reason"] = "invalid_core"
    log(sorted(bad_core), "quarantine", "Invalid identity/date/required field")
    kept = d.loc[scope & ~d.index.isin(bad_core)].copy()
    # Canonical key components are parsed before duplicate checks.
    kept["match_id"] = kept.tourney_id + ":" + pd.to_numeric(kept.match_num).astype("Int64").astype("string")
    content = [c for c in schema["required"] if c not in {"source_file", "source_row"}]
    exact_mask = kept.duplicated(subset=content, keep="first")
    duplicates = kept.loc[exact_mask].copy()
    duplicates["duplicate_reason"] = "exact_duplicate_keep_first"
    log(duplicates.index, "drop_exact_duplicate", "Identical content, ignoring source row/file")
    kept = kept.loc[~exact_mask].copy()
    conflict_mask = kept.match_id.duplicated(keep=False)
    conflict = kept.loc[conflict_mask].copy()
    conflict["quarantine_reason"] = "conflicting_match_id"
    log(conflict.index, "quarantine", "Same match ID has conflicting content; retain no arbitrary winner")
    quarantine = pd.concat([quarantine, conflict], axis=0, ignore_index=False)
    kept = kept.loc[~conflict_mask].copy()

    # Optional invalid metadata are set missing. An invalid serve cell invalidates
    # the whole player's serve block to prevent inconsistent derived percentages.
    warnings = issues.loc[issues.severity.eq("warning") & issues.row_index.isin(kept.index)]
    for idx, field in warnings[["row_index", "field"]].drop_duplicates().itertuples(index=False):
        fields = [field]
        if field.startswith(("w_", "l_")):
            fields = [field[:2] + stat for stat in SERVE]
        for f in fields:
            if pd.notna(kept.at[idx, f]):
                kept.at[idx, f] = pd.NA
                log([idx], "set_missing", "Invalid optional value or inconsistent serve block", f)
    for col, spec in schema["properties"].items():
        dtype = spec["x-csv"]["dtype"]
        if dtype in {"integer", "number"}:
            kept[col] = pd.to_numeric(kept[col], errors="coerce").astype("Int64" if dtype == "integer" else "Float64")
    kept["tournament_start_date"] = pd.to_datetime(kept.tourney_date, format="%Y%m%d").dt.strftime("%Y-%m-%d").astype("string")
    kept["season"] = kept.source_season.astype("Int64")
    kept["tournament_start_year"] = pd.to_datetime(kept.tournament_start_date).dt.year.astype("Int64")
    kept["surface_group"] = kept.surface.fillna("Unknown")
    kept["score_status"] = kept.score.map(score_status).astype("string")
    kept["is_completed"] = kept.score_status.eq("completed")
    kept["rank_pair_available"] = kept.winner_rank.notna() & kept.loser_rank.notna() & kept.winner_rank.ne(kept.loser_rank)
    kept["rank_gap"] = kept.winner_rank - kept.loser_rank
    kept["is_upset"] = kept.winner_rank.gt(kept.loser_rank).where(kept.rank_pair_available).astype("boolean")
    kept["winner_rank_group"] = rank_group(kept.winner_rank)
    kept["loser_rank_group"] = rank_group(kept.loser_rank)
    # Sensitivity flag, not deletion: a very long match can be a legitimate record.
    kept["duration_review_flag"] = kept.minutes.notna() & ((kept.minutes < 20) | (kept.minutes > 360))
    kept["total_aces"] = kept.w_ace + kept.l_ace
    kept["total_double_faults"] = kept.w_df + kept.l_df
    for prefix in ("w", "l"):
        for name, numerator, denominator in [
            ("ace_rate", kept[f"{prefix}_ace"], kept[f"{prefix}_svpt"]),
            ("first_serve_in_rate", kept[f"{prefix}_1stIn"], kept[f"{prefix}_svpt"]),
            ("first_serve_win_rate", kept[f"{prefix}_1stWon"], kept[f"{prefix}_1stIn"]),
            ("second_serve_win_rate", kept[f"{prefix}_2ndWon"], kept[f"{prefix}_svpt"] - kept[f"{prefix}_1stIn"]),
            ("break_point_save_rate", kept[f"{prefix}_bpSaved"], kept[f"{prefix}_bpFaced"])]:
            kept[f"{prefix}_{name}"] = (numerator / denominator.where(denominator.gt(0))).astype("Float64")
    kept = kept.sort_values(["season", "tourney_id", "match_num"]).reset_index(drop=True)
    flow = {"raw_rows": len(d), "excluded_scope_rows": len(excluded),
            "in_scope_rows": int(scope.sum()), "quarantined_rows": len(quarantine),
            "exact_duplicates_removed": len(duplicates), "processed_rows": len(kept),
            "optional_cells_set_missing": sum(a["action"] == "set_missing" for a in actions)}
    assert len(d) == len(excluded) + len(quarantine) + len(duplicates) + len(kept)
    assert kept.match_id.is_unique
    return CleanResult(kept, excluded, quarantine, duplicates, issues,
                       pd.DataFrame(actions, columns=["row_index", "source_file", "source_row", "action", "field", "detail"]), flow)


def player_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """Two player-perspective rows per match; wins + losses are explicit."""
    frames = []
    for role, prefix, won in (("winner", "w", 1), ("loser", "l", 0)):
        d = matches[["match_id", "season", "surface_group", "best_of", "score_status", "is_completed"]].copy()
        for suffix in ["id", "name", "rank", "age", "hand"]:
            d[f"player_{suffix}"] = matches[f"{role}_{suffix}"]
        d["rank_group"] = rank_group(d.player_rank)
        d["won"] = won
        for stat in SERVE + ["ace_rate", "first_serve_in_rate", "first_serve_win_rate", "second_serve_win_rate", "break_point_save_rate"]:
            d[stat] = matches[f"{prefix}_{stat}"]
        frames.append(d)
    return pd.concat(frames, ignore_index=True)
