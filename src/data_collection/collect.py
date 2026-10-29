"""Download immutable source files; verify every cached file before using it."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def collect(root: Path, config: dict, offline: bool = False) -> dict:
    """Fetch CSVs and source documentation pinned to config's full commit SHA.

    Offline mode requires an existing manifest and validates bytes against it.
    A changed cached file is an error, never silently accepted or overwritten.
    """
    raw = root / "data/raw"
    prov = root / "data/provenance"
    raw.mkdir(parents=True, exist_ok=True)
    prov.mkdir(parents=True, exist_ok=True)
    manifest_path = prov / "source_manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    identity = {k: config[k] for k in ("source_repository", "source_commit", "start_season", "end_season")}
    if old and any(old[k] != v for k, v in identity.items()):
        raise ValueError("Source config differs from manifest; use a separate project/snapshot directory.")
    if offline and not old:
        raise FileNotFoundError("Offline mode requires data/provenance/source_manifest.json")
    records = {r["path"]: r for r in old["files"]} if old else {}
    session = requests.Session()
    session.headers["User-Agent"] = "TennisDataScienceAcademicProject/1.0"
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    specs = [(f"atp/atp_matches_{y}.csv", raw / f"atp_matches_{y}.csv")
             for y in range(config["start_season"], config["end_season"] + 1)]
    specs += [(p, prov / p.split("/")[-1]) for p in
              ["README.md", "LICENSE", "atp/UPSTREAM_README.md", "atp/matches_data_dictionary.txt"]]
    files = []
    for remote, target in specs:
        relative = target.relative_to(root).as_posix()
        url = f"https://raw.githubusercontent.com/{config['source_repository']}/{config['source_commit']}/{remote}"
        prior = records.get(relative)
        if target.exists() and prior:
            content = target.read_bytes()
            if sha256(content) != prior["sha256"]:
                raise ValueError(f"Checksum mismatch: {relative}. Restore original bytes before rerunning.")
            files.append(prior)
            continue
        if offline:
            raise FileNotFoundError(f"Missing cached source: {relative}")
        response = session.get(url, timeout=(15, 90))
        response.raise_for_status()
        content = response.content
        row_count = len(pd.read_csv(BytesIO(content))) if target.suffix == ".csv" else None
        target.with_suffix(target.suffix + ".tmp").write_bytes(content)
        target.with_suffix(target.suffix + ".tmp").replace(target)
        files.append({"path": relative, "url": url, "sha256": sha256(content),
                      "bytes": len(content), "rows": row_count,
                      "downloaded_at_utc": datetime.now(timezone.utc).isoformat()})
        print(f"Collected {relative}: {row_count if row_count is not None else len(content)}")
    manifest = {**identity, "original_repository": config["original_repository"],
                "attribution": "Jeff Sackmann / Tennis Abstract", "license": "CC BY-NC-SA 4.0",
                "files": files}
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def load_raw(root: Path, config: dict) -> pd.DataFrame:
    """Keep original lexical values; add traceable file/row/season metadata."""
    frames = []
    for year in range(config["start_season"], config["end_season"] + 1):
        name = f"atp_matches_{year}.csv"
        frame = pd.read_csv(root / "data/raw" / name, dtype="string")
        frame["source_season"] = str(year)
        frame["source_file"] = name
        frame["source_row"] = pd.Series(range(2, len(frame) + 2), dtype="string")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)
