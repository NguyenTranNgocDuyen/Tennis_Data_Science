from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from src.preprocessing.common_semantics import common_round,bracket_size,api_semantics
from src.preprocessing.unified import (IdentityResolver,SemanticError,connect_unified,
    merge_contributions,source_to_common)
from src.analysis.unified_load import load_unified
from src.data_collection.api_store import connect
from src.data_collection.api_batch import ingest
from src.observability import Observer

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('rid,size,expected',[(4,32,'R32'),(4,128,'R128'),(5,128,'R64'),(7,128,'R16'),
    (9,None,'QF'),(10,None,'SF'),(12,None,'F'),(8,None,'RR'),(4,None,None),(5,16,None),(24,32,None)])
def test_round_is_remaining_slots_not_ordinal(rid,size,expected):
    assert common_round(rid,size)==expected


def draw_payload(size):
    return {'singles':[{'roundId':rnd,'draw':i,'tournamentId':20001} for rnd,n in [(4,size//2),(9,4),(10,2),(12,1)] for i in range(1,n+1)]}


def test_bracket_capacity_includes_byes_but_requires_complete_slots():
    payload=draw_payload(32)
    payload['singles'][0]['isBye']=True
    assert bracket_size(payload,20001)==32
    payload['singles'].pop(0)
    assert bracket_size(payload,20001) is None


def test_bracket_cannot_mix_edition_ids():
    payload=draw_payload(32);payload['singles'][0]['tournamentId']=999
    assert bracket_size(payload,20001) is None


@pytest.fixture
def reference():
    return pd.DataFrame([
        {'player_id':'111111','name_first':'Demo Player','name_last':'1001','dob':'19900101','ioc':'AAA'},
        {'player_id':'222222','name_first':'Demo Player','name_last':'1002','dob':'19910101','ioc':'BBB'}],dtype='string')


@pytest.fixture
def historical(good_row):
    d=good_row.copy()
    for role,pid,num,ioc in [('winner','111111','1001','AAA'),('loser','222222','1002','BBB')]:
        d.loc[0,role+'_id']=pid;d.loc[0,role+'_name']='Demo Player '+num;d.loc[0,role+'_ioc']=ioc
    d.loc[0,['source_season','tourney_id','tourney_date','tourney_name','tourney_level','round','score','best_of','draw_size','minutes']]=[
        '2026','2026-demo','20261026','Demo Tour','A','QF','6-3 6-4','3','32','90']
    for col in d:
        if col.startswith(('w_','l_')):d.loc[0,col]=pd.NA
    return d


def aliases():return {'series':[{'key':'demo','name':'Demo Tour','aliases':['Demo Tour','Sponsor Demo Tour']} ]}


def test_id_namespace_and_exact_linkage(tmp_path,historical,reference):
    db=connect_unified(tmp_path/'common.db')
    try:
        resolver=IdentityResolver(db,historical,reference,aliases())
        pid,method=resolver.player('rapidapi_tennis',1001,'Demo Player 1001','AAA')
        assert pid==111111 and method=='unique_full_name_ioc'
        pid,method=resolver.player('rapidapi_tennis',111111,'Different Person','AAA')
        assert pid==1_000_111_111 and method=='source_scoped_unmatched'
    finally:db.close()


def test_homonym_without_same_birthdate_never_auto_merged(tmp_path,historical,reference):
    other=reference.iloc[0].copy();other['player_id']='333333';other['dob']='20000101'
    ref=pd.concat([reference,pd.DataFrame([other])],ignore_index=True)
    db=connect_unified(tmp_path/'common.db')
    try:
        resolver=IdentityResolver(db,historical,ref,aliases())
        pid,method=resolver.player('rapidapi_tennis',1001,'Demo Player 1001','AAA')
        assert method=='source_scoped_ambiguous' and pid!=111111
    finally:db.close()


def test_duplicate_source_id_merges_with_full_name_country_and_birthdate(tmp_path,historical,reference):
    other=reference.iloc[0].copy();other['player_id']='333333'
    ref=pd.concat([reference,pd.DataFrame([other])],ignore_index=True)
    db=connect_unified(tmp_path/'common.db')
    try:
        resolver=IdentityResolver(db,historical,ref,aliases())
        assert resolver.github_ids[333333]==111111
        assert resolver.player('rapidapi_tennis',1001,'Demo Player 1001','AAA')[0]==111111
    finally:db.close()


def test_editions_with_same_series_same_year_different_weeks_are_distinct(tmp_path,historical,reference):
    db=connect_unified(tmp_path/'common.db')
    try:
        resolver=IdentityResolver(db,historical,reference,aliases())
        a=resolver.edition('github','2026-demo','Demo Tour',2026,'2026-10-26','A','Hard',32)
        b=resolver.edition('rapidapi_tennis','20001','Sponsor Demo Tour',2026,'2026-10-26','A','Hard',32)
        c=resolver.edition('rapidapi_tennis','20002','Sponsor Demo Tour',2026,'2026-11-09','A','Hard',32)
        assert a['id']==b['id'] and a['id']!=c['id']
    finally:db.close()


def contribution(provider,row,key='match'):
    return {'provider':provider,'source_key':key,'row_json':json.dumps(row)}


def test_missing_api_value_never_erases_known_historical_value():
    base={'winner_id':'1','loser_id':'2','score':'6-3 6-4','round':'QF','best_of':'3','minutes':'90','w_ace':None}
    api={**base,'minutes':None,'w_ace':'8'}
    value,provenance=merge_contributions([contribution('github',base),contribution('rapidapi_tennis',api)])
    assert value['minutes']=='90' and value['w_ace']=='8'
    assert provenance['field_sources']['w_ace'].startswith('rapidapi_tennis:')


def test_conflicting_outcome_never_silently_overwrites():
    base={'winner_id':'1','loser_id':'2','score':'6-3 6-4','round':'QF','best_of':'3'}
    with pytest.raises(SemanticError,match='Conflicting'):
        merge_contributions([contribution('github',base),contribution('rapidapi_tennis',{**base,'score':'6-0 6-0'})])


def test_season_override_and_match_day_are_separate():
    row={'date':'2026-12-30T12:00:00Z','roundId':9,'tournament':{'id':20001}}
    semantics=api_semantics(row,{}, {'season':'2027'})
    assert semantics['season']==2027 and semantics['season_method']=='explicit_override'
    assert row['date'].startswith('2026')


def test_relocated_indoor_lyon_does_not_merge_with_old_clay_lyon():
    config=json.loads((ROOT/'config/tournament_aliases.json').read_text())
    group=next(g for g in config['series'] if g['key']=='marseille_lyon_indoor')
    assert 'Marseille' in group['aliases'] and 'Lyon' not in group['aliases']


def test_unknown_edition_in_overlap_year_requires_review(tmp_path,historical,reference):
    db=connect_unified(tmp_path/'common.db')
    try:
        resolver=IdentityResolver(db,historical,reference,aliases())
        with pytest.raises(SemanticError,match='historical-overlap'):
            resolver.edition('rapidapi_tennis','unknown','Unverified Tournament',2026,'2026-10-26','A','Hard',32)
    finally:db.close()


def test_incremental_common_load_insert_update_idempotency_and_overlap(tmp_path,historical,reference,monkeypatch):
    for folder in ['config','data/schemas','data/mappings','data/reference']:(tmp_path/folder).mkdir(parents=True,exist_ok=True)
    for name in ['project.json','unified.json','tennis_format_rules.json']:
        (tmp_path/'config'/name).write_text((ROOT/'config'/name).read_text())
    (tmp_path/'config/tournament_aliases.json').write_text(json.dumps(aliases()))
    for name in ['tennis_schema.json','tennis_common_schema.json']:(tmp_path/'data/schemas'/name).write_text((ROOT/'data/schemas'/name).read_text())
    for name in ['player_overrides.csv','edition_overrides.csv']:(tmp_path/'data/mappings'/name).write_text((ROOT/'data/mappings'/name).read_text())
    (tmp_path/'data/reference/github_players_manifest.json').write_text(json.dumps({'sha256':'fixture'}))
    (tmp_path/'data/reference/api_editions.json').write_text(json.dumps({'20001':{'draw_size':32,'raw_path':'fixture'}}))
    monkeypatch.setattr('src.analysis.unified_load.collect',lambda *a,**k:None)
    monkeypatch.setattr('src.analysis.unified_load.load_raw',lambda *a,**k:historical)
    monkeypatch.setattr('src.analysis.unified_load.ensure_player_reference',lambda *a,**k:reference)
    monkeypatch.setattr('src.analysis.unified_load.load_draw_reference',lambda *a,**k:{'20001':{'draw_size':32,'raw_path':'fixture'}})
    api_db=connect(tmp_path/'api.db');common_db=connect_unified(tmp_path/'common.db')
    api_row=json.loads((ROOT/'tests/fixtures/rapidapi/results_page_1.json').read_text())['data'][0]
    api_cfg=json.loads((ROOT/'config/api_batch.json').read_text());api_cfg['max_stats_requests_per_run']=0
    class Client:
        def __init__(self,*a,**kw):pass
        def available(self):return 0
        def get(self,*a,**kw):return {'data':[api_row],'hasNextPage':False,'pageNo':1},'fixture.json'
    ingest(api_db,api_cfg,tmp_path/'raw',start=date(2026,10,22),end=date(2026,10,28),client_factory=Client)
    cfg=json.loads((ROOT/'config/unified.json').read_text())
    obs_cfg=json.loads((ROOT/'config/observability.json').read_text())
    def load():
        observer=Observer(tmp_path,'unified_weekly','test',config=obs_cfg)
        try:return load_unified(tmp_path,common_db,api_db,cfg,observer)
        finally:observer.close()
    try:
        a=load()
        assert a['inserted']==1 and a['total_matches']==1 and a['source_api_records']==1
        b=load()
        assert b['inserted']==0 and b['updated']==0 and b['unchanged']==1 and b['source_unchanged']==2
        with api_db:api_db.execute('UPDATE matches SET source_path=?',('new-raw-location.json',))
        refreshed=load()
        assert refreshed['inserted']==0 and refreshed['updated']==0 and refreshed['unchanged']==1
        with api_db:
            api_db.execute('UPDATE matches SET stats_json=?',(json.dumps({'1001':{'aces':8,'firstServeOf':60}}),))
        c=load()
        assert c['inserted']==0 and c['updated']==1
        ptr=json.loads((tmp_path/'runs/unified/CURRENT.json').read_text())
        frame=pd.read_csv(tmp_path/'runs/unified'/ptr['snapshot']/'tennis_matches.csv')
        assert len(frame)==1 and frame.iloc[0]['minutes']==90 and frame.iloc[0]['w_ace']==8
        # A winner/score correction must be held as a conflict, not overwrite GitHub.
        changed=deepcopy(api_row);changed['result']='6-0 6-0'
        with api_db:api_db.execute('UPDATE matches SET payload_json=?',(json.dumps(changed),))
        previous=(tmp_path/'runs/unified/CURRENT.json').read_bytes()
        with pytest.raises(SemanticError,match='No canonical matches'):load()
        assert common_db.execute('SELECT COUNT(*) FROM match_conflicts').fetchone()[0]==2
        assert (tmp_path/'runs/unified/CURRENT.json').read_bytes()==previous
    finally:api_db.close();common_db.close()
