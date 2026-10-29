"""Vectorized schema checks plus tennis-specific relational constraints."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ISSUE_COLUMNS = ["row_index", "source_file", "source_row", "field", "rule", "severity", "value"]


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_frame(frame: pd.DataFrame, schema: dict, allow_features: bool = False) -> pd.DataFrame:
    """Validate lexical CSV values using the shared schema's x-csv rules.

    error = core identity invalid (quarantine); warning = optional field invalid
    (set missing). Duplicates are errors handled with an explicit separate policy.
    Missing optional values are allowed and counted separately in quality reports.
    """
    missing = set(schema["required"]) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if not allow_features and set(frame.columns) - set(schema["properties"]):
        raise ValueError(f"Unexpected input columns: {sorted(set(frame.columns) - set(schema['properties']))}")
    if not frame.index.is_unique:
        raise ValueError("Validation requires a unique DataFrame index")
    issues = []

    def add(mask, field, rule, severity="warning"):
        for idx in frame.index[pd.Series(mask, index=frame.index).fillna(False)]:
            row = frame.loc[idx]
            issues.append({"row_index": int(idx), "source_file": row.get("source_file"),
                           "source_row": row.get("source_row"), "field": field, "rule": rule,
                           "severity": severity, "value": str(row.get(field, ""))})

    numeric = {}
    for col, spec in schema["properties"].items():
        if col not in frame:
            continue
        rules = spec["x-csv"]
        severity = "error" if rules.get("core") else "warning"
        s = frame[col].astype("string").str.strip().replace("", pd.NA)
        if rules.get("core"):
            add(s.isna(), col, "required_value", severity)
        if rules["dtype"] in ("integer", "number"):
            n = pd.to_numeric(s, errors="coerce")
            numeric[col] = n
            add(s.notna() & n.isna(), col, "numeric_parse", severity)
            if rules["dtype"] == "integer":
                add(n.notna() & n.mod(1).ne(0), col, "integer_required", severity)
            if "minimum" in rules:
                add(n.lt(rules["minimum"]), col, "below_minimum", severity)
            if "maximum" in rules:
                add(n.gt(rules["maximum"]), col, "above_maximum", severity)
        if rules["dtype"] == "date8":
            parsed = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
            add(s.notna() & (parsed.isna() | ~s.str.fullmatch(r"\d{8}", na=False)), col, "date_parse", severity)
        if "enum" in rules:
            add(s.notna() & ~s.isin(rules["enum"]), col, "enum", severity)

    add(numeric["winner_id"].eq(numeric["loser_id"]), "winner_id", "same_player", "error")
    season = numeric["source_season"]
    date_year = pd.to_datetime(frame["tourney_date"], format="%Y%m%d", errors="coerce").dt.year
    # Early next-season events can start in December of the previous calendar year.
    add(date_year.notna() & ~(date_year.eq(season) | (date_year.eq(season - 1) & frame["tourney_date"].astype("string").str[4:6].eq("12"))),
        "tourney_date", "date_outside_season", "error")
    integer_season = season.where(season.mod(1).eq(0)).astype("Int64").astype("string")
    add(frame["tourney_id"].astype("string").str[:4].ne(integer_season),
        "tourney_id", "id_season_mismatch", "error")
    for p in ("w", "l"):
        pairs = [(f"{p}_1stIn", f"{p}_svpt"), (f"{p}_1stWon", f"{p}_1stIn"),
                 (f"{p}_bpSaved", f"{p}_bpFaced"), (f"{p}_ace", f"{p}_svpt")]
        for a, b in pairs:
            add(numeric[a].gt(numeric[b]), a, f"greater_than_{b}")
        second = numeric[f"{p}_svpt"] - numeric[f"{p}_1stIn"]
        add(numeric[f"{p}_2ndWon"].gt(second), f"{p}_2ndWon", "second_wins_gt_second_points")
        add(numeric[f"{p}_df"].gt(second), f"{p}_df", "double_faults_gt_second_points")
        add((numeric[f"{p}_2ndWon"] + numeric[f"{p}_df"]).gt(second), f"{p}_2ndWon", "second_wins_plus_df_gt_second_points")
    return pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def summarize_validation(frame: pd.DataFrame, issues: pd.DataFrame) -> dict:
    return {"rows": len(frame), "columns": len(frame.columns), "issues": len(issues),
            "rows_with_issues": int(issues.row_index.nunique()),
            "error_rows": int(issues.loc[issues.severity.eq("error"), "row_index"].nunique()),
            "warning_rows": int(issues.loc[issues.severity.eq("warning"), "row_index"].nunique())}
