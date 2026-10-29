"""Schema and semantic edge cases; no dependency on network availability."""
import json
import hashlib

import pandas as pd
import pytest
from jsonschema import Draft202012Validator

from src.data_collection import collect
from src.data_validation import validate_frame


def test_json_schema_is_valid(schema,good_row):
    Draft202012Validator.check_schema(schema)
    record={c:None if pd.isna(v) else str(v) for c,v in good_row.iloc[0].items()}
    Draft202012Validator(schema).validate(record)
    assert validate_frame(good_row,schema).empty


def test_missing_column_stops(good_row,schema):
    with pytest.raises(ValueError,match='Missing required columns'):
        validate_frame(good_row.drop(columns='winner_id'),schema)


def test_unexpected_input_column_stops(good_row,schema):
    with pytest.raises(ValueError,match='Unexpected input columns'):
        validate_frame(good_row.assign(typo=1),schema)


@pytest.mark.parametrize('field,value,rule,severity',[
    ('winner_name',pd.NA,'required_value','error'),
    ('winner_id','abc','numeric_parse','error'),
    ('match_num','1.5','integer_required','error'),
    ('source_season','2025.5','integer_required','error'),
    ('tourney_date','20250230','date_parse','error'),
    ('winner_rank','-1','below_minimum','warning'),
    ('minutes','0','below_minimum','warning'),
    ('surface','Ice','enum','warning'),
    ('winner_age','200','above_maximum','warning'),
    ('w_ace','1.5','integer_required','warning')])
def test_invalid_values(good_row,schema,field,value,rule,severity):
    d=good_row.copy(); d.loc[0,field]=value
    found=validate_frame(d,schema)
    assert ((found.field==field)&(found.rule==rule)&(found.severity==severity)).any()


def test_missing_optional_values_allowed(good_row,schema):
    d=good_row.copy(); d.loc[0,['winner_rank','loser_rank','minutes','surface']]=pd.NA
    assert validate_frame(d,schema).empty


def test_same_player_is_core_error(good_row,schema):
    d=good_row.copy(); d.loc[0,'winner_id']=d.loc[0,'loser_id']
    assert 'same_player' in set(validate_frame(d,schema).rule)


def test_serve_relational_error(good_row,schema):
    d=good_row.copy(); d.loc[0,'w_1stWon']='99999'
    assert 'greater_than_w_1stIn' in set(validate_frame(d,schema).rule)


def test_previous_december_season_is_allowed(good_row,schema):
    d=good_row.copy(); d.loc[0,'source_season']='2025'; d.loc[0,'tourney_id']='2025-test'; d.loc[0,'tourney_date']='20241227'
    assert validate_frame(d,schema).empty
    d.loc[0,'tourney_date']='20241127'
    assert 'date_outside_season' in set(validate_frame(d,schema).rule)


def test_offline_requires_manifest(tmp_path,config):
    with pytest.raises(FileNotFoundError,match='requires'):
        collect(tmp_path,config,offline=True)


def test_cache_corruption_rejected(tmp_path,config):
    p=tmp_path/'data/provenance'; p.mkdir(parents=True)
    raw=tmp_path/'data/raw'; raw.mkdir()
    filename=f"atp_matches_{config['start_season']}.csv"
    (raw/filename).write_bytes(b'tampered')
    record={'path':'data/raw/'+filename,'sha256':hashlib.sha256(b'original').hexdigest()}
    old={k:config[k] for k in ['source_repository','source_commit','start_season','end_season']}
    old['files']=[record]
    (p/'source_manifest.json').write_text(json.dumps(old))
    with pytest.raises(ValueError,match='Checksum mismatch'):
        collect(tmp_path,config,offline=True)
