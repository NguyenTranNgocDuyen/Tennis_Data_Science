"""SQLite source-of-truth, request audit and transactional batch watermarks."""
import json
from pathlib import Path
import sqlite3

DDL='''
CREATE TABLE IF NOT EXISTS batch_runs (
 run_id TEXT PRIMARY KEY, mode TEXT NOT NULL, start_date TEXT NOT NULL,
 end_date TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
 status TEXT NOT NULL, summary_json TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS requests (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, request_day TEXT NOT NULL,
 path TEXT NOT NULL, params TEXT NOT NULL, requested_at TEXT NOT NULL,
 status INTEGER, raw_path TEXT, sha256 TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS requests_day ON requests(request_day);
CREATE TABLE IF NOT EXISTS matches (
 provider TEXT NOT NULL, stable_key TEXT NOT NULL, archive_id TEXT,
 match_date TEXT NOT NULL, tournament_id TEXT NOT NULL, round_id INTEGER NOT NULL,
 player_low INTEGER NOT NULL, player_high INTEGER NOT NULL,
 payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
 stats_json TEXT, stats_checked_at TEXT,
 source_path TEXT NOT NULL, stats_source_path TEXT,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
 changed_at TEXT NOT NULL, run_id TEXT NOT NULL,
 PRIMARY KEY(provider,stable_key)
);
CREATE TABLE IF NOT EXISTS sync_state (
 provider TEXT PRIMARY KEY, last_success_date TEXT NOT NULL, run_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rejected_records (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, source_path TEXT NOT NULL,
 reason TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_hits (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, source_run_id TEXT NOT NULL,
 source_request_id INTEGER NOT NULL, path TEXT NOT NULL, params TEXT NOT NULL,
 raw_path TEXT NOT NULL, sha256 TEXT NOT NULL, used_at TEXT NOT NULL
);
'''


def connect(path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=30)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript(DDL)
    # Additive migration for existing installations; raw/IDs/data remain intact.
    for table,column,declaration in [('batch_runs','parent_run_id','TEXT'),
                                     ('batch_runs','recovery_mode',"TEXT DEFAULT 'live'"),
                                     ('requests','is_network','INTEGER NOT NULL DEFAULT 1')]:
        columns={row[1] for row in db.execute(f'PRAGMA table_info({table})')}
        if column not in columns:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
    db.commit()
    return db


def canonical_json(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
