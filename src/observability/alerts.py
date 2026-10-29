"""Persistent Telegram outbox. Network delivery never controls the data transaction."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

import requests
from .messages import format_notification

DDL='''
CREATE TABLE IF NOT EXISTS alerts (
 id INTEGER PRIMARY KEY, operation_id TEXT, fingerprint TEXT, priority TEXT,
 stage TEXT, code TEXT, message TEXT, tags TEXT, created REAL,
 status TEXT, attempts INTEGER DEFAULT 0, next_attempt REAL DEFAULT 0,
 suppressed_count INTEGER DEFAULT 0, sent_at REAL, telegram_message_id TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS alert_groups (
 fingerprint TEXT PRIMARY KEY, last_queued REAL, suppressed INTEGER DEFAULT 0,
 last_alert INTEGER
);
'''


class AlertOutbox:
    def __init__(self,path:Path,config,session=None,clock=time.time):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path,timeout=15)
        self.db.row_factory=sqlite3.Row
        self.db.executescript(DDL)
        if 'context_json' not in {r[1] for r in self.db.execute('PRAGMA table_info(alerts)')}:
            self.db.execute('ALTER TABLE alerts ADD COLUMN context_json TEXT')
            self.db.commit()
        self.config=config
        self.session=session or requests.Session()
        self.clock=clock

    def enqueue(self,operation_id,pipeline,stage,priority,code,message,tags,dry_run=False,context=None):
        now=self.clock()
        # Per-operation summaries must not suppress the success of a distinct run.
        scope=operation_id if priority in {'P3','P4'} and code=='RUN_SUMMARY' else ''
        routing=os.environ.get('TELEGRAM_CHAT_ID','')
        fingerprint=hashlib.sha256(json.dumps([pipeline,stage,priority,code,scope,routing,dry_run]).encode()).hexdigest()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            group=self.db.execute('SELECT * FROM alert_groups WHERE fingerprint=?',(fingerprint,)).fetchone()
            suppressed=bool(group and now-group['last_queued']<self.config['dedup_seconds'])
            status='dry_run' if dry_run else 'suppressed' if suppressed else 'pending'
            count=group['suppressed'] if group and not suppressed else 0
            cur=self.db.execute('''INSERT INTO alerts(operation_id,fingerprint,priority,stage,code,message,tags,created,status,suppressed_count)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',(operation_id,fingerprint,priority,stage,code,message,json.dumps(tags),now,status,count))
            self.db.execute('UPDATE alerts SET context_json=? WHERE id=?',(json.dumps(context,ensure_ascii=False) if context else None,cur.lastrowid))
            if suppressed:
                self.db.execute('UPDATE alert_groups SET suppressed=suppressed+1 WHERE fingerprint=?',(fingerprint,))
            else:
                self.db.execute('INSERT INTO alert_groups VALUES(?,?,0,?) ON CONFLICT(fingerprint) DO UPDATE SET last_queued=excluded.last_queued,suppressed=0,last_alert=excluded.last_alert',
                                (fingerprint,now,cur.lastrowid))
        return cur.lastrowid,status

    def _queue_digests(self):
        now=self.clock()
        with self.db:
            for group in self.db.execute('SELECT * FROM alert_groups WHERE suppressed>0 AND last_queued<=?',(now-self.config['dedup_seconds'],)).fetchall():
                prior=self.db.execute('SELECT * FROM alerts WHERE id=?',(group['last_alert'],)).fetchone()
                if not prior or prior['status']=='dry_run':
                    continue
                cur=self.db.execute('''INSERT INTO alerts(operation_id,fingerprint,priority,stage,code,message,tags,created,status,suppressed_count)
                  VALUES(?,?,?,?,?,?,?,?,?,?)''',(prior['operation_id'],prior['fingerprint'],prior['priority'],prior['stage'],prior['code'],prior['message'],prior['tags'],now,'pending',group['suppressed']))
                self.db.execute('UPDATE alerts SET context_json=? WHERE id=?',(prior['context_json'],cur.lastrowid))
                self.db.execute('UPDATE alert_groups SET last_queued=?,suppressed=0,last_alert=? WHERE fingerprint=?',(now,cur.lastrowid,group['fingerprint']))

    def flush(self,token=None,chat_id=None):
        config=self.config
        if not config['enabled']:
            return {'delivery':'disabled','sent':0}
        token=token or os.environ.get('TELEGRAM_BOT_TOKEN','').strip()
        chat_id=chat_id or os.environ.get('TELEGRAM_CHAT_ID','').strip()
        if not token or not chat_id:
            return {'delivery':'not_configured','sent':0}
        if config.get('recipient_type')=='private' and (not str(chat_id).isdigit() or int(chat_id)<=0):
            return {'delivery':'recipient_type_mismatch','sent':0}
        self._queue_digests()
        now=self.clock();sent=0;failed=0
        with self.db:
            self.db.execute("UPDATE alerts SET status='expired' WHERE status IN ('pending','retry') AND created<?",(now-config['message_expiry_hours']*3600,))
        # Claim before HTTP. Ambiguous delivery after a crash/timeout may duplicate;
        # the operation/alert ID makes that visible, never promise exactly once.
        for _ in range(config['max_messages_per_flush']):
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                row=self.db.execute("SELECT * FROM alerts WHERE status IN ('pending','retry') AND next_attempt<=? ORDER BY priority,id LIMIT 1",(now,)).fetchone()
                if not row:
                    break
                self.db.execute("UPDATE alerts SET status='sending',attempts=attempts+1,next_attempt=? WHERE id=?",(now+60,row['id']))
            try:
                text=format_notification(dict(row))
            except Exception:
                text=f"⚠️ Có thông báo pipeline cần kiểm tra trong log.\nMã tra cứu: run={str(row['operation_id'])[:8]} · tin={row['id']}\n#{row['priority']}"
            status='retry';error='transport_error';message_id=None;wait=60
            try:
                response=self.session.post(f'https://api.telegram.org/bot{token}/sendMessage',
                    json={'chat_id':chat_id,'text':text[:3900],'disable_notification':row['priority'] in {'P3','P4'}},
                    timeout=config['timeout_seconds'],allow_redirects=False)
                try: body=response.json()
                except ValueError: body={}
                if (response.status_code==200 and isinstance(body,dict) and body.get('ok') is True
                    and isinstance(body.get('result'),dict) and body['result'].get('message_id') is not None):
                    status='sent';error=None;message_id=str(body['result']['message_id'])
                elif response.status_code in {400,401,403,404}:
                    status='dead_letter';error=f'HTTP_{response.status_code}'
                else:
                    error=f'HTTP_{response.status_code}'
                    retry=(body.get('parameters') or {}).get('retry_after',60) if isinstance(body,dict) else 60
                    wait=max(1,min(int(retry),3600))
            except (requests.RequestException,ValueError,TypeError,AttributeError):
                # Exception strings contain the bot-token URL; never persist them.
                pass
            if row['attempts']+1>=config['max_delivery_attempts'] and status=='retry':
                status='dead_letter'
            with self.db:
                self.db.execute('UPDATE alerts SET status=?,last_error=?,next_attempt=?,sent_at=?,telegram_message_id=? WHERE id=?',
                    (status,error,now+wait,now if status=='sent' else None,message_id,row['id']))
            sent+=int(status=='sent');failed+=int(status!='sent')
        # Recover claims from a process killed during sendMessage, on the next flush.
        with self.db:
            self.db.execute("UPDATE alerts SET status='retry',last_error='delivery_interrupted' WHERE status='sending' AND next_attempt<=?",(now,))
        return {'delivery':'processed','sent':sent,'failed':failed}

    def close(self):
        self.db.close()
