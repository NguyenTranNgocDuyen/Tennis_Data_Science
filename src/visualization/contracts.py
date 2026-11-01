"""Loading and minimal semantic validation for published analysis tables."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


RATE_COLUMNS = {"upset_rate", "win_rate", "rate", "missing_rate", "share",
                "raw_missing_rate", "clean_missing_rate"}


def load_contract(contract_path: Path) -> dict[str, Any]:
    """Load the versioned table contract without modifying it."""
    return json.loads(Path(contract_path).read_text(encoding="utf-8"))


def validate_table(frame: pd.DataFrame, table_name: str, contract: dict[str, Any]) -> None:
    """Raise ValueError when a table cannot safely be visualized under its contract."""
    try:
        definition = contract["tables"][table_name]
    except KeyError as exc:
        raise ValueError(f"Table {table_name!r} is absent from the table contract") from exc
    required = {column["name"] for column in definition["columns"]}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{table_name} is missing required columns: {', '.join(missing)}")
    for column in required.intersection(RATE_COLUMNS):
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if not values.between(0, 1).all():
            raise ValueError(f"{table_name}.{column} must be a proportion in [0, 1]")


def load_table(table_name: str, tables_dir: Path, contract_path: Path) -> pd.DataFrame:
    """Read a UTF-8 hand-off CSV and validate required columns and proportions."""
    contract = load_contract(contract_path)
    try:
        filename = contract["tables"][table_name]["file"]
    except KeyError as exc:
        raise ValueError(f"Table {table_name!r} is absent from the table contract") from exc
    frame = pd.read_csv(Path(tables_dir) / filename)
    validate_table(frame, table_name, contract)
    return frame
