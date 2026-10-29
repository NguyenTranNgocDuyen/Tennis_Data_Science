import pandas as pd
import pytest

from src.preprocessing import clean_matches, player_matches
from src.preprocessing.clean import score_status
from src.data_validation import validate_frame


def test_input_not_mutated(good_row,schema,config):
    before=good_row.copy(deep=True)
    clean_matches(good_row,schema,config)
    pd.testing.assert_frame_equal(before,good_row)


def test_exact_duplicate_removed(good_row,schema,config):
    d=pd.concat([good_row,good_row],ignore_index=True); d.loc[1,'source_row']='9999'
    r=clean_matches(d,schema,config)
    assert len(r.matches)==1 and len(r.duplicates)==1 and len(r.quarantine)==0


def test_conflict_quarantines_entire_key(good_row,schema,config):
    d=pd.concat([good_row,good_row],ignore_index=True); d.loc[1,'score']='6-0 6-0'; d.loc[1,'source_row']='9999'
    if good_row.loc[0,'score']=='6-0 6-0':
        d.loc[1,'score']='6-1 6-1'
    r=clean_matches(d,schema,config)
    assert len(r.quarantine)==2 and r.matches.empty


def test_bad_core_quarantined(good_row,schema,config):
    d=good_row.copy(); d.loc[0,'winner_name']=pd.NA
    r=clean_matches(d,schema,config)
    assert r.matches.empty and len(r.quarantine)==1


def test_optional_rank_missing_not_imputed(good_row,schema,config):
    d=good_row.copy(); d.loc[0,'winner_rank']='-1'
    r=clean_matches(d,schema,config)
    assert pd.isna(r.matches.loc[0,'winner_rank'])
    assert pd.isna(r.matches.loc[0,'is_upset'])
    assert not r.matches.loc[0,'rank_pair_available']
    assert r.matches.loc[0,'winner_rank_group']=='Unknown'
    assert validate_frame(r.matches,schema,allow_features=True).empty


def test_bad_serve_block_removed_only_for_affected_player(good_row,schema,config):
    d=good_row.copy(); d.loc[0,'w_1stWon']='99999'
    r=clean_matches(d,schema,config)
    assert r.matches.loc[0,[c for c in r.matches if c.startswith('w_')]].isna().all()
    assert r.matches.loc[0,'l_svpt']==int(good_row.loc[0,'l_svpt'])


def test_zero_denominator_is_missing(good_row,schema,config):
    d=good_row.copy(); d.loc[0,['w_bpFaced','w_bpSaved']]='0'
    m=clean_matches(d,schema,config).matches
    assert pd.isna(m.loc[0,'w_break_point_save_rate'])


def test_extreme_positive_duration_retained(good_row,schema,config):
    d=good_row.copy(); d.loc[0,'minutes']='500'
    m=clean_matches(d,schema,config).matches
    assert len(m)==1 and m.loc[0,'minutes']==500 and m.loc[0,'duration_review_flag']


@pytest.mark.parametrize('name',['Atp Cup','United Cup','Laver Cup','NextGen Finals','Next Gen Finals','Rio Olympics'])
def test_event_name_filter_case_variants(good_row,schema,config,name):
    d=good_row.copy(); d.loc[0,'tourney_name']=name; d.loc[0,'tourney_level']='A'
    r=clean_matches(d,schema,config)
    assert r.matches.empty and len(r.excluded)==1


def test_season_not_replaced_by_calendar_year(good_row,schema,config):
    d=good_row.copy(); d.loc[0,'source_season']='2025'; d.loc[0,'tourney_id']='2025-test'; d.loc[0,'tourney_date']='20241227'
    m=clean_matches(d,schema,config).matches
    assert m.loc[0,'season']==2025 and m.loc[0,'tournament_start_year']==2024


@pytest.mark.parametrize('score,status',[
    ('6-3 7-6(4)','completed'),('6-3 1-0 RET','retired'),('W/O','walkover'),
    ('6-1 DEF','defaulted'),('ABN','abandoned'),(pd.NA,'unknown'),('invalid','unknown'),
    ('7-6(3) 6-7(1) [10-8]','completed')])
def test_score_status(score,status):
    assert score_status(score)==status


def test_player_view_has_two_sides(good_row,schema,config):
    m=clean_matches(good_row,schema,config).matches
    p=player_matches(m)
    assert len(p)==2 and p.won.sum()==1 and p.player_id.nunique()==2
