from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from src.data_collection.api_store import connect
from src.data_collection.api_batch import ingest,choose_window
from src.data_collection.rapidapi_client import RapidAPIClient,APIError,QuotaExceeded
from src.preprocessing.rapidapi_adapter import stable_key,to_canonical,validate_stats,RecordError
from src.analysis.api_export import export_api

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'tests/fixtures/rapidapi'


@pytest.fixture
def api_config():
    c=json.loads((ROOT/'config/api_batch.json').read_text())
    c.update(max_stats_requests_per_run=0,minimum_request_interval_seconds=0)
    return c


@pytest.fixture
def api_row():
    return json.loads((FIX/'results_page_1.json').read_text())['data'][0]


@pytest.fixture
def db(tmp_path):
    con=connect(tmp_path/'test.sqlite3')
    yield con
    con.close()


def page(rows,more=False,number=1):
    return {'data':rows,'hasNextPage':more,'pageNo':number,'pageSize':500}


class FakeBatchClient:
    def __init__(self,responses):
        self.responses=list(responses);self.calls=[]
    def available(self): return 100
    def get(self,path,params=None):
        self.calls.append((path,params))
        answer=self.responses.pop(0)
        if isinstance(answer,Exception): raise answer
        return answer,'synthetic-response.json'


def run(db,config,tmp_path,answers):
    client=FakeBatchClient(answers)
    answer=ingest(db,config,tmp_path/'raw',start=date(2026,10,22),end=date(2026,10,28),
                  client_factory=lambda *args:client)
    return answer,client


def test_stable_key_ignores_recycled_archive_id_and_winner_orientation(api_row):
    other=deepcopy(api_row);other['id']=1;other['matchId']=1
    assert stable_key(other)==stable_key(api_row)
    other['player1'],other['player2']=other['player2'],other['player1']
    other['player1Id'],other['player2Id']=other['player2Id'],other['player1Id']
    assert stable_key(other)==stable_key(api_row)


def test_pages_complete_then_upsert_is_idempotent(db,api_config,tmp_path,api_row):
    a,_=run(db,api_config,tmp_path,[page([api_row],True),page([],False,2)])
    assert a['inserted']==1 and a['pages']==2
    other=deepcopy(api_row);other.update(id=8,matchId=8)
    b,_=run(db,api_config,tmp_path,[page([other])])
    assert b['inserted']==0 and b['unchanged']==1
    assert db.execute('SELECT COUNT(*) FROM matches').fetchone()[0]==1
    assert db.execute('SELECT archive_id FROM matches').fetchone()[0]=='8'


def test_reused_numeric_id_does_not_overwrite_different_match(db,api_config,tmp_path,api_row):
    other=deepcopy(api_row)
    other['roundId']=10
    run(db,api_config,tmp_path,[page([api_row,other])])
    assert db.execute('SELECT COUNT(*) FROM matches').fetchone()[0]==2


def test_result_correction_updates_same_row(db,api_config,tmp_path,api_row):
    run(db,api_config,tmp_path,[page([api_row])])
    row=deepcopy(api_row);row['result']='6-2 6-2'
    b,_=run(db,api_config,tmp_path,[page([row])])
    assert b['updated']==1
    assert json.loads(db.execute('SELECT payload_json FROM matches').fetchone()[0])['result']=='6-2 6-2'


@pytest.mark.parametrize('failure',[
    APIError('HTTP failure'),QuotaExceeded('quota'),
    {'data':[]},page([],True,2),page([],False,99)])
def test_incomplete_discovery_never_commits_matches_or_watermark(db,api_config,tmp_path,api_row,failure):
    with pytest.raises(APIError):
        run(db,api_config,tmp_path,[page([api_row],True),failure])
    assert db.execute('SELECT COUNT(*) FROM matches').fetchone()[0]==0
    assert db.execute('SELECT COUNT(*) FROM sync_state').fetchone()[0]==0
    assert db.execute('SELECT status FROM batch_runs').fetchone()[0]=='failed'


def test_repeated_page_rejected(db,api_config,tmp_path,api_row):
    with pytest.raises(APIError,match='Repeated'):
        run(db,api_config,tmp_path,[page([api_row],True),page([api_row],True,2)])


def test_invalid_selected_record_retained_and_batch_failed(db,api_config,tmp_path,api_row):
    del api_row['player1']['name']
    with pytest.raises(APIError,match='Invalid result'):
        run(db,api_config,tmp_path,[page([api_row])])
    assert db.execute('SELECT COUNT(*) FROM rejected_records').fetchone()[0]==1


def test_scope_and_qualifying_filtered(db,api_config,tmp_path):
    rows=json.loads((FIX/'results_page_1.json').read_text())['data']
    answer,_=run(db,api_config,tmp_path,[page(rows)])
    assert answer['selected']==1 and answer['out_of_scope']==2


def test_empty_valid_date_advances_watermark(db,api_config,tmp_path):
    result,_=run(db,api_config,tmp_path,[page([])])
    assert result['selected']==0
    assert db.execute('SELECT last_success_date FROM sync_state').fetchone()[0]=='2026-10-28'


def test_gap_recovery_and_disjoint_backfill(db,api_config,tmp_path,api_row):
    with db:
        db.execute('INSERT INTO sync_state VALUES(?,?,?)',('rapidapi_tennis','2026-10-01','old'))
    start,end=choose_window(db,api_config,today=date(2026,10,29))
    assert start==date(2026,10,2) and end==date(2026,10,28)
    run(db,api_config,tmp_path,[page([api_row])])
    assert db.execute('SELECT last_success_date FROM sync_state').fetchone()[0]=='2026-10-01'


def test_stats_fetched_after_all_pages_and_only_within_cap(db,api_config,tmp_path,api_row):
    api_config['max_stats_requests_per_run']=1
    stats=json.loads((FIX/'stats_1001-1002-20001-9.json').read_text())
    answer,client=run(db,api_config,tmp_path,[page([api_row],True),page([],False,2),stats])
    assert answer['stats_fetched']==1
    assert client.calls[2][0].endswith('/1001-1002-20001-9/stats')
    assert client.calls[2][1]['source']=='game'
    again,client=run(db,api_config,tmp_path,[page([api_row])])
    assert again['stats_fetched']==0 and len(client.calls)==1


def test_foreign_stats_player_rejected(api_row):
    stats={'data':{'player1Stats':{'player1Id':9999,'aces':1}}}
    with pytest.raises(RecordError): validate_stats(stats,api_row)


def test_stats_mapping_uses_player_id_not_array_position(api_row,schema):
    stats=json.loads((FIX/'stats_1001-1002-20001-9.json').read_text())
    parsed=validate_stats(stats,api_row)
    row=to_canonical(api_row,parsed,schema,'fixture')
    assert row['w_ace']=='5' and row['l_ace']=='3'
    assert row['winner_rank'] is None and row['minutes'] is None


def test_result_correction_drops_stale_stats_when_enrichment_disabled(db,api_config,tmp_path,api_row):
    api_config['max_stats_requests_per_run']=1
    stats=json.loads((FIX/'stats_1001-1002-20001-9.json').read_text())
    run(db,api_config,tmp_path,[page([api_row]),stats])
    assert json.loads(db.execute('SELECT stats_json FROM matches').fetchone()[0])
    api_config['max_stats_requests_per_run']=0
    api_row['result']='6-2 6-4'
    run(db,api_config,tmp_path,[page([api_row])])
    stored=db.execute('SELECT stats_json,stats_checked_at,stats_source_path FROM matches').fetchone()
    assert stored['stats_json']=='{}'
    assert stored['stats_checked_at'] is None and stored['stats_source_path'] is None


def test_partial_conflicting_identity_rejected(api_row):
    api_row['player1']['id']=999
    with pytest.raises(RecordError,match='Conflicting'): stable_key(api_row)


def test_failed_export_keeps_previous_current(db,api_config,tmp_path,schema,config,api_row,monkeypatch):
    run(db,api_config,tmp_path,[page([api_row])])
    output=tmp_path/'export'
    export_api(db,ROOT,output,api_config,schema,config,'test')
    before=(output/'CURRENT.json').read_bytes()
    def broken(*a,**kw): raise RuntimeError('simulated export failure')
    monkeypatch.setattr('src.analysis.api_export.build_tables',broken)
    with pytest.raises(RuntimeError,match='simulated'):
        export_api(db,ROOT,output,api_config,schema,config,'test')
    assert (output/'CURRENT.json').read_bytes()==before
    assert not list((output/'snapshots').glob('.building-*'))


def test_api_export_uses_B_and_isolates_quarantine(db,api_config,tmp_path,schema,config):
    first=json.loads((FIX/'results_page_1.json').read_text())
    second=json.loads((FIX/'results_page_2.json').read_text())
    second['data'][-1]['best_of']=9  # Invalid provided format must not be repaired by a missing-value rule.
    run(db,api_config,tmp_path,[first,second])
    output=tmp_path/'exports'
    pointer=export_api(db,ROOT,output,api_config,schema,config,'test')
    snapshot=output/pointer['snapshot']
    assert pointer['n_matches']==2 and pointer['n_tables']==14
    q=pd.read_csv(snapshot/'quarantine.csv')
    assert len(q)==1
    issues=pd.read_csv(snapshot/'validation_issues.csv')
    assert 'best_of' in issues.field.tolist()
    assert pd.read_csv(snapshot/'tennis_matches.csv').winner_rank.isna().all()
    assert json.loads((output/'CURRENT.json').read_text())==pointer


class Response:
    def __init__(self,status=200,payload=None,content=None):
        self.status_code=status
        self.content=content if content is not None else json.dumps(payload or {'data':[],'hasNextPage':False}).encode()


class Session:
    def __init__(self,responses): self.responses=list(responses);self.calls=[]
    def get(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        r=self.responses.pop(0)
        if isinstance(r,Exception): raise r
        return r


def http(db,api_config,tmp_path,responses):
    session=Session(responses)
    client=RapidAPIClient('SECRET_TEST_KEY',api_config,db,tmp_path/'raw','test',session=session,sleep=lambda _:None)
    return client,session


def test_http_credentials_headers_only_and_raw_redaction(db,api_config,tmp_path):
    client,session=http(db,api_config,tmp_path,[Response(payload={'data':[],'echo':'SECRET_TEST_KEY'})])
    _,path=client.get('/tennis/v2/atp/results/2026-10-28')
    args,kwargs=session.calls[0]
    assert 'SECRET_TEST_KEY' not in args[0]
    assert kwargs['headers']['X-RapidAPI-Key']=='SECRET_TEST_KEY'
    assert kwargs['allow_redirects'] is False
    assert 'SECRET_TEST_KEY' not in Path(path).read_text()
    assert 'SECRET_TEST_KEY' not in Path(path).with_suffix('.meta.json').read_text()


def test_quota_shared_between_clients_and_runs(db,api_config,tmp_path):
    api_config['daily_request_budget']=1
    a,_=http(db,api_config,tmp_path,[Response()])
    a.get('/tennis/v2/atp/results/2026-10-28')
    b,session=http(db,api_config,tmp_path,[Response()])
    with pytest.raises(QuotaExceeded): b.get('/tennis/v2/atp/results/2026-10-28')
    assert session.calls==[]


def test_retries_are_counted_against_budget(db,api_config,tmp_path):
    client,session=http(db,api_config,tmp_path,[Response(503),Response(503),Response(200)])
    client.get('/tennis/v2/atp/results/2026-10-28')
    assert len(session.calls)==3
    assert db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==3


@pytest.mark.parametrize('response',[Response(401),Response(403),Response(429),Response(302),Response(200,content=b'invalid json'),Response(200,payload={'error':'bad'})])
def test_http_failures_do_not_masquerade_as_empty_success(db,api_config,tmp_path,response):
    client,_=http(db,api_config,tmp_path,[response])
    with pytest.raises(APIError): client.get('/tennis/v2/atp/results/2026-10-28')


def test_transport_retry_never_logs_secret_exception(db,api_config,tmp_path):
    api_config['max_retries']=0
    client,_=http(db,api_config,tmp_path,[requests.ConnectionError('secret SECRET_TEST_KEY')])
    with pytest.raises(APIError) as exc: client.get('/tennis/v2/atp/results/2026-10-28')
    assert 'SECRET_TEST_KEY' not in str(exc.value)
    assert db.execute('SELECT error FROM requests').fetchone()[0]=='transport_error'
