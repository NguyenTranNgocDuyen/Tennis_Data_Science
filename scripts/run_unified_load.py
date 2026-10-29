"""Weekly incremental common-schema load. Defaults to stored raw/SQLite only."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.observability import Observer
from src.observability.runtime import load_env
from src.data_collection.api_store import connect
from src.data_collection.common_reference import ensure_player_reference,refresh_draw_reference
from src.preprocessing.unified import connect_unified
from src.analysis.unified_load import load_unified


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collect',action='store_true',help='Reconcile 30 API days before loading; weekly scheduled mode')
    p.add_argument('--refresh-reference',action='store_true',help='Fetch missing draw metadata within the existing shared quota')
    p.add_argument('--dry-notify',action='store_true',help='Keep operation logs without Telegram delivery')
    args=p.parse_args()
    load_env(ROOT/'.env')
    if args.dry_notify:os.environ['PIPELINE_ALERTS_DRY_RUN']='1'
    cfg=json.loads((ROOT/'config/unified.json').read_text())
    api_cfg=json.loads((ROOT/'config/api_batch.json').read_text())
    observer=Observer(ROOT,'unified_weekly')
    summary={}
    try:
        if args.collect:
            with observer.task('api_reconciliation'):
                env={**os.environ,'PIPELINE_ALERTS_DRY_RUN':'1','PIPELINE_PARENT_RUN_ID':observer.id}
                result=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/run_api_batch.py'),'--reconcile'],
                    cwd=ROOT,env=env,capture_output=True,text=True)
                if result.returncode:raise RuntimeError('API reconciliation failed; inspect child operation log. Common dataset unchanged.')
        with observer.task('reference'):
            ensure_player_reference(ROOT,offline=not args.refresh_reference)
        api_path=ROOT/api_cfg['database'];common_path=ROOT/cfg['database']
        api_path.parent.mkdir(parents=True,exist_ok=True);common_path.parent.mkdir(parents=True,exist_ok=True)
        with api_path.with_suffix('.lock').open('a') as api_lock,common_path.with_suffix('.lock').open('a') as common_lock:
            try:
                fcntl.flock(api_lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(common_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Another API/common load is running; retry later') from None
            api_db=connect(api_path);common_db=connect_unified(common_path)
            try:
                if args.refresh_reference:
                    with observer.task('reference'):
                        reference,ref_summary=refresh_draw_reference(ROOT,api_db,api_cfg,cfg['reference_request_limit'],observer=observer)
                        observer.event('reference.ready','reference',**ref_summary)
                summary=load_unified(ROOT,common_db,api_db,cfg,observer)
            finally:api_db.close();common_db.close()
        observer.finish(summary)
        print(json.dumps({'operation_id':observer.id,**summary},ensure_ascii=False,indent=2))
    except BaseException as exc:
        observer.finish(summary,error=exc);raise
    finally:observer.close()


if __name__=='__main__':main()
