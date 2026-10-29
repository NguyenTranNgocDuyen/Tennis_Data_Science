import pandas as pd
import pytest

from src.preprocessing import clean_matches
from src.analysis import build_tables


def fixture_matches(good_row,schema,config):
    d=pd.concat([good_row]*3,ignore_index=True)
    for i in d.index:
        d.loc[i,'match_num']=str(9000+i)
        d.loc[i,'source_row']=str(100+i)
    d.loc[:,'surface']='Hard'; d.loc[:,'score']='6-3 6-3'
    d.loc[0,['winner_rank','loser_rank']]=['20','10']
    d.loc[1,['winner_rank','loser_rank']]=['5','50']
    d.loc[2,['winner_rank','loser_rank']]=[pd.NA,'10']
    return d,clean_matches(d,schema,config).matches


def test_upset_denominator_and_wins(good_row,schema,config):
    d,m=fixture_matches(good_row,schema,config)
    t=build_tables(m,d,schema)
    s=t['surface_summary'].iloc[0]
    assert s.n_matches==3 and s.n_ranked_completed==2 and s.n_upsets==1 and s.upset_rate==.5
    p=t['rank_group_performance']
    assert p.n_appearances.sum()==6 and p.wins.sum()==3


def test_retirements_excluded_from_play_metrics(good_row,schema,config):
    d,_=fixture_matches(good_row,schema,config); d.loc[0,'score']='6-1 RET'
    m=clean_matches(d,schema,config).matches
    t=build_tables(m,d,schema)
    assert t['surface_summary'].n_matches.sum()==3
    assert t['surface_summary'].n_completed.sum()==2
    assert t['rank_group_performance'].n_appearances.sum()==4
    assert t['surface_summary'].n_upsets.sum()==0


def test_serve_rate_is_weighted_and_paired(good_row,schema,config):
    d,_=fixture_matches(good_row,schema,config)
    # Clear all serve blocks then populate coherent values with unequal denominators.
    for prefix in ['w','l']:
        cols=[c for c in d if c.startswith(prefix+'_')]
        d.loc[:,cols]=pd.NA
    d.loc[0,['w_ace','w_svpt']]=['1','10']
    d.loc[1,['w_ace','w_svpt']]=['1','100']
    d.loc[2,['w_ace','w_svpt']]=[pd.NA,'999']
    m=clean_matches(d,schema,config).matches
    a=build_tables(m,d,schema)['serve_by_surface']
    a=a.loc[a.metric.eq('ace_rate')].iloc[0]
    assert a.n_appearances==2 and a.numerator==2 and a.denominator==110
    assert a.rate==pytest.approx(2/110)


def test_unchanged_rerun_is_deterministic(good_row,schema,config):
    d,_=fixture_matches(good_row,schema,config)
    a=clean_matches(d,schema,config); b=clean_matches(d,schema,config)
    pd.testing.assert_frame_equal(a.matches,b.matches)
    ta,tb=build_tables(a.matches,d,schema),build_tables(b.matches,d,schema)
    for name in ta:
        pd.testing.assert_frame_equal(ta[name],tb[name])
