"""Inspect/flush the Telegram outbox, or explicitly send one test message."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.observability import Observer
from src.observability.alerts import AlertOutbox
from src.observability.runtime import load_env


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--status',action='store_true',help='Local delivery counts only; no Telegram request')
    mode.add_argument('--flush',action='store_true',help='Deliver pending alerts; obey retries, dedup and expiry')
    mode.add_argument('--test',action='store_true',help='Send one explicitly requested configuration test to configured chat')
    args=parser.parse_args()
    load_env(ROOT/'.env')
    config=json.loads((ROOT/'config/observability.json').read_text())
    if args.test:
        import os
        if not os.environ.get('TELEGRAM_BOT_TOKEN') or not os.environ.get('TELEGRAM_CHAT_ID'):
            parser.error('Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env before sending a test')
        observer=Observer(ROOT,'telegram_test')
        try:
            observer.alert('telegram','P4','CONFIGURATION_TEST','Personal Telegram notification test from KHDL pipeline. No data payload attached.',['pipeline','test','P4'])
            result=observer.flush()
            statuses=[dict(r) for r in observer.outbox.db.execute('SELECT id,status FROM alerts WHERE operation_id=?',(observer.id,))]
            print(json.dumps({'delivery':result,'test_alerts':statuses},indent=2))
        finally: observer.close()
        return
    box=AlertOutbox(ROOT/'data/monitoring/alerts.sqlite3',config['telegram'])
    try:
        if args.flush: print(json.dumps(box.flush(),indent=2))
        else:
            counts=[dict(r) for r in box.db.execute('SELECT priority,status,COUNT(*) AS count FROM alerts GROUP BY priority,status ORDER BY priority,status')]
            print(json.dumps({'counts':counts,'token_present':bool(__import__('os').environ.get('TELEGRAM_BOT_TOKEN')),
                              'chat_id_present':bool(__import__('os').environ.get('TELEGRAM_CHAT_ID'))},indent=2))
    finally: box.close()


if __name__=='__main__': main()
