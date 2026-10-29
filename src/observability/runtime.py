"""Structured task logs, secret redaction and bounded alert delivery."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import time
import traceback
import uuid

from .alerts import AlertOutbox

ENV_NAMES={'RAPIDAPI_KEY','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'}


def load_env(path):
    if not path.exists(): return
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        if '=' not in line: raise ValueError('Invalid .env syntax; use NAME=value')
        name,value=line.split('=',1);name=name.strip();value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in {'"',"'"}: value=value[1:-1]
        if name in ENV_NAMES and not os.environ.get(name): os.environ[name]=value


def redact(value):
    text=str(value)
    for name in ENV_NAMES:
        secret=os.environ.get(name,'')
        if secret: text=text.replace(secret,'[REDACTED]')
    return re.sub(r'bot\d+:[A-Za-z0-9_-]+','bot[REDACTED]',text)


class Observer:
    def __init__(self,root:Path,pipeline,mode='live',operation_id=None,config=None,session=None):
        self.root,self.pipeline,self.mode=root,pipeline,mode
        self.id=operation_id or uuid.uuid4().hex
        self.config=config or json.loads((root/'config/observability.json').read_text())
        self.dry_run=mode in {'demo','replay','test'} or os.environ.get('PIPELINE_ALERTS_DRY_RUN')=='1'
        logs=root/'logs';(logs/'runs').mkdir(parents=True,exist_ok=True)
        self.logger=logging.getLogger('tennis.'+self.id);self.logger.setLevel(logging.INFO);self.logger.propagate=False
        formatter=logging.Formatter('%(message)s')
        for handler in [RotatingFileHandler(logs/'pipeline.jsonl',maxBytes=self.config['log_max_bytes'],backupCount=self.config['log_backup_count'],encoding='utf-8'),
                        logging.FileHandler(logs/'runs'/f'{self.id}.jsonl',encoding='utf-8')]:
            handler.setFormatter(formatter);self.logger.addHandler(handler)
        self.outbox=AlertOutbox(root/'data/monitoring/alerts.sqlite3',self.config['telegram'],session=session)
        self.started=time.monotonic();self.tasks={};self.warnings=[];self.failed=False
        self.event('pipeline.started',stage='pipeline',mode=mode)

    def event(self,event,stage,priority='P4',**details):
        record={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'operation_id':self.id,
            'parent_operation_id':os.environ.get('PIPELINE_PARENT_RUN_ID'),'pipeline':self.pipeline,
            'mode':self.mode,'stage':stage,'event':event,'priority':priority,**details}
        self.logger.info(redact(json.dumps(record,ensure_ascii=False,default=str)))

    def start_task(self,stage):
        self.tasks[stage]={'start':time.monotonic(),'status':'running'}
        self.event('task.started',stage)

    def end_task(self,stage,**details):
        item=self.tasks.get(stage,{})
        item['status']='succeeded'
        self.event('task.succeeded',stage,duration_seconds=round(time.monotonic()-item.get('start',time.monotonic()),3),**details)

    def fail_task(self,stage,exc):
        name=type(exc).__name__;message=redact(str(exc))
        priority='P1' if isinstance(exc,AssertionError) or any(word in message.lower() for word in ['checksum','integrity','hash mismatch','corrupt']) else 'P2'
        self.event('task.failed',stage,priority=priority,error_type=name,error=message,traceback=traceback.format_exc())
        code=name.upper()
        if 'HTTP 401' in message or 'HTTP 403' in message: code='API_AUTHORIZATION'
        elif '429' in message or 'quota' in message.lower() or 'budget' in message.lower(): code='API_QUOTA'
        elif 'checksum' in message.lower() or 'integrity' in message.lower(): code='RAW_INTEGRITY'
        if not self.failed:
            self.alert(stage,priority,code,f'Task failed: {name}; code={code}. Full redacted error and traceback are in the local log.\nLog: logs/runs/{self.id}.jsonl',['pipeline',stage,'failure',priority])
        self.failed=True
        for task,info in self.tasks.items():
            if info['status']=='running':
                info['status']='failed'
                if task!=stage: self.event('task.interrupted',task,priority=priority,caused_by=stage)

    @contextmanager
    def task(self,stage):
        self.start_task(stage)
        try:
            yield
        except BaseException as exc:
            self.fail_task(stage,exc)
            raise
        else:
            self.end_task(stage)

    def alert(self,stage,priority,code,message,tags,context=None):
        try:
            safe_context=json.loads(redact(json.dumps(context,ensure_ascii=False,default=str))) if context else None
            alert_id,status=self.outbox.enqueue(self.id,self.pipeline,stage,priority,code,redact(message),tags,self.dry_run,safe_context)
        except Exception as exc:
            self.event('alert.persistence_failed','telegram',priority='P1',error_type=type(exc).__name__)
            return
        self.event('alert.queued',stage,priority=priority,alert_id=alert_id,delivery_status=status,code=code)
        if priority in {'P1','P2'} and not self.dry_run: self.flush()

    def flush(self):
        try:
            result=self.outbox.flush()
            self.event('alert.delivery',stage='telegram',**result)
            return result
        except Exception as exc:
            self.event('alert.delivery_failed',stage='telegram',priority='P2',error_type=type(exc).__name__)

    def quality(self,flow):
        n=flow.get('in_scope_rows',flow.get('raw_rows',0));q=flow.get('quarantined_rows',0)
        if q and n:
            ratio=q/n;priority='P2' if ratio>=self.config['quality']['quarantine_error_ratio'] else 'P3'
            message=f'Quarantined {q}/{n} records ({ratio:.1%}); inspect quarantine.csv and validation_issues.csv.'
            self.warnings.append(message)
            self.event('quality.warning',stage='validation',priority=priority,quarantined=q,denominator=n)
            if priority=='P2': self.alert('validation','P2','QUARANTINE_RATIO',message,['pipeline','data_quality','P2'])
        if flow.get('optional_cells_set_missing',0):
            self.warnings.append(f"Invalid optional cells set missing: {flow['optional_cells_set_missing']}")

    def warning(self,stage,code,message):
        self.warnings.append(redact(message))
        self.event('quality.warning',stage,priority='P3',code=code,message=message)

    def finish(self,summary=None,error=None):
        if error and not self.failed: self.fail_task('pipeline',error)
        status='failed' if self.failed or error else 'succeeded_with_warnings' if self.warnings else 'succeeded'
        self.event('pipeline.finished','pipeline',priority='P2' if status=='failed' else 'P3' if self.warnings else 'P4',
                   status=status,duration_seconds=round(time.monotonic()-self.started,3),summary=summary or {},warnings=self.warnings)
        if status!='failed' and (self.config['telegram']['notify_success'] or self.warnings):
            priority='P3' if self.warnings else 'P4'
            context={'pipeline':self.pipeline,'status':status,'summary':summary or {},'warnings':self.warnings,
                     'duration_seconds':round(time.monotonic()-self.started,1)}
            self.alert('pipeline',priority,'RUN_SUMMARY','Quy trình đã hoàn tất; xem ngữ cảnh và log để tra chi tiết.',
                       ['pipeline','summary','success',priority],context)
        if not self.dry_run: self.flush()

    def close(self):
        self.outbox.close()
        for handler in list(self.logger.handlers): handler.close();self.logger.removeHandler(handler)
