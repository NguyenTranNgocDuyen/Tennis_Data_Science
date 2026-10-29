"""Fetch completed ATP main-draw singles; use --demo to verify without a key."""
from __future__ import annotations

import argparse
from datetime import date
import fcntl
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from src.data_collection.api_store import connect
from src.data_collection.api_batch import ingest
from src.data_collection.api_replay import ReplayClient
from src.data_collection.rapidapi_client import APIError
from src.data_validation import load_schema
from src.analysis.api_export import export_api
from src.observability import Observer
from src.observability.runtime import load_env


def load_local_env(path):
    """Supported API/Telegram variables only; never execute shell from .env."""
    load_env(path)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true',help='Synthetic fixtures; no network/key; separate runs/api_demo database')
    parser.add_argument('--start',type=date.fromisoformat)
    parser.add_argument('--end',type=date.fromisoformat)
    parser.add_argument('--reconcile',action='store_true',help='Read last 30 completed UTC days (subject to free quota)')
    parser.add_argument('--export-only',action='store_true',help='Rebuild B outputs from stored API records without HTTP')
    parser.add_argument('--check',action='store_true',help='Validate local configuration/key presence without making a request')
    recovery=parser.add_mutually_exclusive_group()
    recovery.add_argument('--replay-run',help='Offline rebuild from one raw run into isolated runs/api_replay; never HTTP')
    recovery.add_argument('--resume-run',help='Recover same batch: use verified raw, fetch only missing responses')
    recovery.add_argument('--replay-dir',type=Path,help='Offline rebuild directly from raw folder + manifest, even without original SQLite')
    parser.add_argument('--list-runs',action='store_true',help='List recent ingestion runs and their status without API calls')
    args=parser.parse_args(argv)
    if bool(args.start)!=bool(args.end):
        parser.error('Supply both --start and --end')
    if args.reconcile and args.start:
        parser.error('--reconcile cannot be combined with explicit dates')
    if (args.replay_run or args.resume_run or args.replay_dir) and (args.export_only or args.reconcile or args.start):
        parser.error('Recovery takes its date window from the source run; do not combine with other window/export flags')
    config=json.loads((ROOT/'config/api_batch.json').read_text())
    project=json.loads((ROOT/'config/project.json').read_text())
    schema=load_schema(ROOT/'data/schemas/tennis_schema.json')
    if config['tour']!='atp' or not 1<=config['daily_request_budget']<=50:
        raise APIError('This free-tier implementation requires ATP and a daily budget between 1 and 50')
    if not 1<=config['page_size']<=500 or config['lookback_days']<1:
        raise APIError('Invalid pagination/lookback configuration')
    if not args.demo:
        load_local_env(ROOT/'.env')
    key=os.environ.get('RAPIDAPI_KEY','').strip()
    if args.check:
        if not args.demo and not key: raise APIError('Missing RAPIDAPI_KEY; configure .env')
        print(json.dumps({'configuration':'valid','key_present':bool(key),'network_requests':0,'mode':'demo' if args.demo else 'live'}))
        return
    db_path=ROOT/config['database']; output=ROOT/config['output_directory']; raw=ROOT/config['raw_directory']
    if args.demo:
        output=ROOT/'runs/api_demo'; db_path=output/'tennis.sqlite3';raw=output/'raw'
    if args.list_runs:
        db=connect(db_path)
        try:
            rows=db.execute('SELECT run_id,mode,recovery_mode,parent_run_id,start_date,end_date,status FROM batch_runs ORDER BY started_at DESC LIMIT 30').fetchall()
            print(json.dumps([dict(r) for r in rows],indent=2))
        finally: db.close()
        return
    observer=Observer(ROOT,'api_batch','replay' if args.replay_run or args.replay_dir else 'demo' if args.demo else 'live')
    source_db=None;source_run=args.replay_run or args.resume_run
    summary={'mode':observer.mode,'operation_id':observer.id}
    try:
        if args.replay_dir:
            from src.data_collection.raw_cache import import_bundle
            output=ROOT/'runs/api_replay/imported'/observer.id
            source_db=connect(output/'raw_index.sqlite3')
            source_run,source_config=import_bundle(args.replay_dir,source_db)
            # Pagination must match the captured requests; interpretation uses
            # current code and scope so a corrected adapter can be re-run.
            config['page_size']=source_config['page_size']
            source=source_db.execute('SELECT * FROM batch_runs WHERE run_id=?',(source_run,)).fetchone()
            args.start,args.end=date.fromisoformat(source['start_date']),date.fromisoformat(source['end_date'])
            db_path=output/'tennis.sqlite3';raw=output/'raw'
        elif source_run:
            source_db=connect(db_path)
            source=source_db.execute('SELECT * FROM batch_runs WHERE run_id=?',(source_run,)).fetchone()
            if not source: raise APIError('Source raw run ID not found; use --list-runs (and --demo for demo storage)')
            if args.resume_run:
                later=source_db.execute("SELECT 1 FROM batch_runs WHERE status='succeeded' AND started_at>? LIMIT 1",(source['started_at'],)).fetchone()
                if later: raise APIError('A newer batch already succeeded. Use isolated --replay-run to avoid overwriting newer data.')
            args.start,args.end=date.fromisoformat(source['start_date']),date.fromisoformat(source['end_date'])
            if args.replay_run:
                output=ROOT/'runs/api_replay'/source_run/observer.id
                db_path=output/'tennis.sqlite3';raw=output/'raw'
        if not args.demo and not args.export_only and not source_run and not key:
            raise APIError('Missing RAPIDAPI_KEY. Configure .env; replay/export-only modes do not need a key.')
        _run_locked(args,config,project,schema,key,db_path,output,raw,observer,source_db,source_run,summary)
        observer.finish(summary)
    except BaseException as exc:
        observer.finish(summary,error=exc)
        raise
    finally:
        if source_db is not None: source_db.close()
        observer.close()


def _run_locked(args,config,project,schema,key,db_path,output,raw,observer,source_db,source_run,summary):
    db_path.parent.mkdir(parents=True,exist_ok=True)
    with db_path.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise APIError('Another API batch/export is running; retry later.') from None
        db=connect(db_path)
        try:
            if not args.export_only:
                start,end=args.start,args.end
                if args.demo and start is None:
                    start,end=date(2026,10,22),date(2026,10,28)
                summary.update(ingest(db,config,raw,key,start,end,
                                     ReplayClient if args.demo else None,args.reconcile,
                                     observer,source_db,source_run,bool(args.replay_run or args.replay_dir),observer.id,observer.mode))
                if not args.demo and not args.replay_run and not args.replay_dir:
                    from src.data_collection.common_reference import refresh_draw_reference
                    with observer.task('reference'):
                        refs,ref_summary=refresh_draw_reference(ROOT,db,config,limit=6,observer=observer)
                        observer.event('reference.ready','reference',**ref_summary)
            with observer.task('snapshot_export'):
                summary['export']=export_api(db,ROOT,output,config,schema,project,summary['mode'],observer)
            (output/'last_run.json').write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps(summary,indent=2))
        finally:
            db.close()


if __name__=='__main__':
    try:
        main()
    except (APIError,ValueError) as exc:
        print(f'Batch stopped: {exc}',file=sys.stderr)
        sys.exit(1)
