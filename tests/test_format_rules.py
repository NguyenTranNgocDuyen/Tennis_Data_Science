from copy import deepcopy
import json
from pathlib import Path
import pytest
from src.preprocessing.rapidapi_adapter import resolve_best_of

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('level,expected',[(2,3),(3,3),(4,5),(7,3)])
def test_verified_2026_main_draw_format(level,expected):
    row=json.loads((ROOT/'tests/fixtures/rapidapi/results_page_1.json').read_text())['data'][0]
    row['best_of']=None;row['tournament']['rankId']=level
    rules=json.loads((ROOT/'config/tennis_format_rules.json').read_text())
    value,source,url=resolve_best_of(row,rules)
    assert value==expected and source=='verified_competition_rule' and url.startswith('https://')


@pytest.mark.parametrize('change', ['year','qualifying','doubles','unknown_level','excluded_event'])
def test_rule_never_fills_outside_verified_scope(change):
    row=json.loads((ROOT/'tests/fixtures/rapidapi/results_page_1.json').read_text())['data'][0]
    row['best_of']=None
    if change=='year':row['date']='2027-01-05T12:00:00Z'
    elif change=='qualifying':row['roundId']=2
    elif change=='doubles':row['player1']['members']=[{'id':1},{'id':2}]
    elif change=='unknown_level':row['tournament']['rankId']=99
    else:row['tournament']['name']='Next Gen Finals'
    rules=json.loads((ROOT/'config/tennis_format_rules.json').read_text())
    assert resolve_best_of(row,rules)[0] is None


def test_provided_value_never_overwritten():
    row={'best_of':9}
    assert resolve_best_of(row,{'anything':True})==(9,'api',None)
