from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest
import requests

from src.data_collection.api_batch import ingest
from src.data_collection.api_store import connect
from src.data_collection.api_replay import ReplayClient
from src.data_collection.raw_cache import import_bundle
from src.data_collection.rapidapi_client import APIError
from src.observability import Observer
from src.observability.alerts import AlertOutbox

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    value=json.loads((ROOT/'config/api_batch.json').read_text())
    value['max_stats_requests_per_run']=20
    return value


@pytest.fixture
def obs_config():
    config=json.loads((ROOT/'config/observability.json').read_text())
    config['telegram']['recipient_type']='any'  # Generic sender supports either; app now opts into private-only.
    return config


def batch(db,cfg,path,**kwargs):
    return ingest(db,cfg,path,start=date(2026,10,22),end=date(2026,10,28),mode='demo',**kwargs)


def test_full_raw_replay_no_network_and_no_api_key(tmp_path,cfg,monkeypatch):
    source=connect(tmp_path/'source.sqlite3');dest=connect(tmp_path/'dest.sqlite3')
    try:
        result=batch(source,cfg,tmp_path/'raw',client_factory=ReplayClient)
        def forbidden(*a,**k): raise AssertionError('Network delegate must never be constructed')
        replay=batch(dest,cfg,tmp_path/'replay',client_factory=forbidden,source_db=source,source_run=result['run_id'],offline=True)
        assert replay['cache_hits']==5 and replay['stats_fetched']==3
        assert dest.execute('SELECT COUNT(*) FROM matches').fetchone()[0]==3
        assert dest.execute('SELECT COUNT(*) FROM requests WHERE is_network=1').fetchone()[0]==0
        assert (tmp_path/'raw'/result['run_id']/'run_manifest.json').exists()
    finally: source.close();dest.close()


def test_resume_partial_batch_only_missing_pages_and_stats(tmp_path,cfg):
    db=connect(tmp_path/'source.sqlite3')
    calls=[]
    class FailSecond(ReplayClient):
        def get(self,path,params=None):
            if (params or {}).get('pageNo')==2: raise APIError('Simulated page 2 failure')
            return super().get(path,params)
    class Track(ReplayClient):
        def get(self,path,params=None):
            calls.append((path,params));return super().get(path,params)
    try:
        with pytest.raises(APIError): batch(db,cfg,tmp_path/'raw',client_factory=FailSecond)
        source=db.execute('SELECT run_id FROM batch_runs').fetchone()[0]
        assert db.execute('SELECT COUNT(*) FROM matches').fetchone()[0]==0
        result=batch(db,cfg,tmp_path/'raw',client_factory=Track,source_db=db,source_run=source)
        assert result['cache_hits']==1 and result['inserted']==3
        assert len(calls)==4
        assert not any((params or {}).get('pageNo')==1 for _,params in calls)
    finally: db.close()


def test_missing_page_offline_fails_without_delegate(tmp_path,cfg):
    db=connect(tmp_path/'source.sqlite3');dest=connect(tmp_path/'dest.sqlite3')
    class FailSecond(ReplayClient):
        def get(self,path,params=None):
            if (params or {}).get('pageNo')==2: raise APIError('failure')
            return super().get(path,params)
    try:
        with pytest.raises(APIError): batch(db,cfg,tmp_path/'raw',client_factory=FailSecond)
        source=db.execute('SELECT run_id FROM batch_runs').fetchone()[0]
        with pytest.raises(APIError,match='offline replay'):
            batch(dest,cfg,tmp_path/'replay',source_db=db,source_run=source,offline=True)
        assert dest.execute('SELECT COUNT(*) FROM sync_state').fetchone()[0]==0
    finally: db.close();dest.close()


def test_raw_hash_mismatch_rejected(tmp_path,cfg):
    db=connect(tmp_path/'source.sqlite3');dest=connect(tmp_path/'dest.sqlite3')
    try:
        run=batch(db,cfg,tmp_path/'raw',client_factory=ReplayClient)
        file=Path(db.execute('SELECT raw_path FROM requests ORDER BY id LIMIT 1').fetchone()[0])
        file.write_text('{}')
        with pytest.raises(APIError,match='checksum'):
            batch(dest,cfg,tmp_path/'replay',source_db=db,source_run=run['run_id'],offline=True)
    finally: db.close();dest.close()


def test_raw_directory_import_does_not_need_original_database(tmp_path,cfg):
    db=connect(tmp_path/'source.sqlite3')
    run=batch(db,cfg,tmp_path/'raw',client_factory=ReplayClient)
    db.close()
    (tmp_path/'source.sqlite3').unlink()
    index=connect(tmp_path/'index.sqlite3');dest=connect(tmp_path/'dest.sqlite3')
    try:
        source,loaded=import_bundle(tmp_path/'raw'/run['run_id'],index)
        replay=batch(dest,loaded,tmp_path/'replay',source_db=index,source_run=source,offline=True)
        assert replay['cache_hits']==5
    finally: index.close();dest.close()


def test_offline_without_stats_keeps_explicit_partial_coverage(tmp_path,cfg):
    db=connect(tmp_path/'source.sqlite3');dest=connect(tmp_path/'dest.sqlite3')
    minimal=deepcopy(cfg);minimal['max_stats_requests_per_run']=0
    try:
        run=batch(db,minimal,tmp_path/'raw',client_factory=ReplayClient)
        replay=batch(dest,cfg,tmp_path/'replay',source_db=db,source_run=run['run_id'],offline=True)
        assert replay['stats_missing_raw']==3 and replay['stats_fetched']==0
    finally: db.close();dest.close()


class Response:
    def __init__(self,status=200,body=None):
        self.status_code=status;self.body=body or {'ok':True,'result':{'message_id':88}}
    def json(self): return self.body


class Telegram:
    def __init__(self,responses): self.responses=list(responses);self.calls=[]
    def post(self,*a,**k):
        self.calls.append((a,k))
        response=self.responses.pop(0)
        if isinstance(response,Exception): raise response
        return response


def enqueue(box,priority='P2',run='run-1',code='API_DOWN',message='Upstream unavailable',dry_run=False):
    return box.enqueue(run,'api_batch','discovery',priority,code,message,['pipeline','api',priority],dry_run)


def test_telegram_delivery_and_priority_tags(tmp_path,obs_config):
    session=Telegram([Response()]);box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'],session)
    try:
        enqueue(box)
        assert box.flush('token','-100123')['sent']==1
        _,kwargs=session.calls[0]
        assert '#P2' in kwargs['json']['text'] and 'run=run-1' in kwargs['json']['text']
        assert kwargs['json']['chat_id']=='-100123' and 'parse_mode' not in kwargs['json']
        assert not kwargs['json']['disable_notification']
        assert box.db.execute('SELECT status FROM alerts').fetchone()[0]=='sent'
    finally: box.close()


def test_duplicate_error_is_suppressed_then_digest_sent(tmp_path,obs_config):
    clock=[1000.0];session=Telegram([Response(),Response()])
    box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'],session,clock=lambda:clock[0])
    try:
        enqueue(box);box.flush('token','chat')
        _,status=enqueue(box,run='run-2');assert status=='suppressed'
        clock[0]+=1801
        result=box.flush('token','chat')
        assert result['sent']==1
        assert 'Đã gộp 1 cảnh báo lặp' in session.calls[-1][1]['json']['text']
    finally: box.close()


def test_escalation_not_suppressed_by_lower_priority(tmp_path,obs_config):
    box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'])
    try:
        enqueue(box,priority='P2')
        assert enqueue(box,priority='P1')[1]=='pending'
    finally: box.close()


def test_success_summary_once_per_distinct_run(tmp_path,obs_config):
    box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'])
    try:
        assert enqueue(box,'P4','one','RUN_SUMMARY')[1]=='pending'
        assert enqueue(box,'P4','two','RUN_SUMMARY')[1]=='pending'
    finally: box.close()


def test_missing_credentials_preserve_outbox(tmp_path,obs_config,monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN',raising=False);monkeypatch.delenv('TELEGRAM_CHAT_ID',raising=False)
    box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'])
    try:
        enqueue(box)
        assert box.flush()['delivery']=='not_configured'
        assert box.db.execute('SELECT status FROM alerts').fetchone()[0]=='pending'
    finally: box.close()


def test_telegram_retry_after_and_durable_retry(tmp_path,obs_config):
    clock=[1000.0];session=Telegram([Response(429,{'ok':False,'parameters':{'retry_after':120}}),Response()])
    box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'],session,clock=lambda:clock[0])
    try:
        enqueue(box);box.flush('token','chat')
        assert box.db.execute('SELECT status FROM alerts').fetchone()[0]=='retry'
        assert box.flush('token','chat')['sent']==0
        clock[0]+=121
        assert box.flush('token','chat')['sent']==1
    finally: box.close()


def test_invalid_token_goes_to_dead_letter(tmp_path,obs_config):
    session=Telegram([Response(401,{'ok':False})]);box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'],session)
    try:
        enqueue(box);box.flush('token','chat')
        assert box.db.execute('SELECT status FROM alerts').fetchone()[0]=='dead_letter'
    finally: box.close()


def test_private_only_configuration_blocks_group_without_sending(tmp_path,obs_config):
    obs_config['telegram']['recipient_type']='private'
    session=Telegram([]);box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'],session)
    try:
        enqueue(box)
        assert box.flush('token','-100123')['delivery']=='recipient_type_mismatch'
        assert session.calls==[]
        assert box.db.execute('SELECT status FROM alerts').fetchone()[0]=='pending'
    finally: box.close()


def test_private_only_configuration_delivers_to_personal_chat(tmp_path,obs_config):
    obs_config['telegram']['recipient_type']='private'
    session=Telegram([Response()]);box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'],session)
    try:
        enqueue(box)
        assert box.flush('token','123456')['sent']==1
        assert session.calls[0][1]['json']['chat_id']=='123456'
    finally: box.close()


def test_expired_alerts_not_delivered_and_flush_cap_enforced(tmp_path,obs_config):
    clock=[1000.0];cfg=deepcopy(obs_config['telegram']);cfg['max_messages_per_flush']=1
    session=Telegram([Response()]);box=AlertOutbox(tmp_path/'alerts.db',cfg,session,clock=lambda:clock[0])
    try:
        enqueue(box,code='OLD')
        clock[0]+=25*3600
        enqueue(box,code='NEW_ONE');enqueue(box,code='NEW_TWO')
        assert box.flush('token','chat')['sent']==1
        states=[r[0] for r in box.db.execute('SELECT status FROM alerts ORDER BY id')]
        assert states==['expired','sent','pending']
    finally: box.close()


def test_notification_persistence_error_does_not_fail_data_run(tmp_path,obs_config,monkeypatch):
    observer=Observer(tmp_path,'test','test',config=obs_config)
    def broken(*a,**kw): raise RuntimeError('outbox write failure')
    monkeypatch.setattr(observer.outbox,'enqueue',broken)
    try:
        observer.finish({'data':'complete'})
        assert not observer.failed
    finally: observer.close()


def test_warning_still_summarized_when_success_notifications_disabled(tmp_path,obs_config):
    obs_config['telegram']['notify_success']=False
    observer=Observer(tmp_path,'test','test',config=obs_config)
    try:
        observer.quality({'in_scope_rows':10,'quarantined_rows':1})
        observer.finish()
        assert observer.outbox.db.execute('SELECT priority FROM alerts').fetchone()[0]=='P3'
    finally: observer.close()


def test_transport_error_does_not_store_token_url(tmp_path,obs_config):
    session=Telegram([requests.ConnectionError('https://api.telegram.org/bot123:SECRET/sendMessage')])
    box=AlertOutbox(tmp_path/'alerts.db',obs_config['telegram'],session)
    try:
        enqueue(box);box.flush('123:SECRET','chat')
        assert box.db.execute('SELECT last_error FROM alerts').fetchone()[0]=='transport_error'
    finally: box.close()


def test_demo_does_not_send_real_telegram_even_with_credentials(tmp_path,obs_config,monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','123:SECRET');monkeypatch.setenv('TELEGRAM_CHAT_ID','-100999')
    session=Telegram([]);observer=Observer(tmp_path,'test','demo',config=obs_config,session=session)
    try:
        with observer.task('task'): pass
        observer.finish({'count':1})
        assert session.calls==[]
        assert observer.outbox.db.execute('SELECT status FROM alerts').fetchone()[0]=='dry_run'
    finally: observer.close()


def test_structured_logs_are_redacted_and_capture_task_failure(tmp_path,obs_config,monkeypatch):
    monkeypatch.setenv('RAPIDAPI_KEY','SECRET_API_VALUE')
    observer=Observer(tmp_path,'test','test',config=obs_config)
    operation=observer.id
    try:
        with pytest.raises(ValueError):
            with observer.task('validation'): raise ValueError('SECRET_API_VALUE bad input')
        observer.finish(error=ValueError('bad input'))
    finally: observer.close()
    text=(tmp_path/'logs/runs'/f'{operation}.jsonl').read_text()
    assert 'SECRET_API_VALUE' not in text
    events=[json.loads(line) for line in text.splitlines()]
    assert any(e['event']=='task.failed' and e['stage']=='validation' for e in events)
    assert events[-1]['status']=='failed'


def test_observer_quality_summary_and_alert_transport_failure_are_nonfatal(tmp_path,obs_config,monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','token');monkeypatch.setenv('TELEGRAM_CHAT_ID','chat')
    session=Telegram([requests.Timeout('token')])
    observer=Observer(tmp_path,'test','live',config=obs_config,session=session)
    try:
        observer.quality({'in_scope_rows':10,'quarantined_rows':1})
        observer.finish({'export':'complete'})
        row=observer.outbox.db.execute('SELECT * FROM alerts').fetchone()
        assert row['priority']=='P3' and row['status']=='retry'
        assert not observer.failed
    finally: observer.close()
