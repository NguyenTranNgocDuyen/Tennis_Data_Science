import json
from pathlib import Path
import pandas as pd

from src.analysis import build_tables
from src.analysis.reporting import write_table_contract
from src.preprocessing import clean_matches

ROOT=Path(__file__).resolve().parents[1]


def test_empty_completed_population_has_stable_columns(good_row,schema,config):
    d=good_row.copy(); d.loc[0,'score']='RET'
    m=clean_matches(d,schema,config).matches
    tables=build_tables(m,d,schema)
    assert list(tables['duration_by_surface_format'].columns)==['surface_group','best_of','n_matches','n_duration','missing_duration','mean_minutes','std_minutes','p25_minutes','median_minutes','p75_minutes','p95_minutes','max_minutes']
    assert list(tables['serve_by_surface'].columns)==['surface_group','metric','n_appearances','n_possible_appearances','numerator','denominator','rate']
    assert tables['rank_group_performance'].empty


def test_sample_and_real_table_contracts_match(tmp_path,schema,config):
    sample=pd.read_csv(ROOT/'data/sample/tennis_sample.csv',dtype='string')
    result=clean_matches(sample,schema,config)
    tables=build_tables(result.matches,sample,schema)
    file=tmp_path/'table_contract.json'
    write_table_contract(file,tables)
    sample_contract=json.loads(file.read_text())
    real_contract=json.loads((ROOT/'reports/tables/table_contract.json').read_text())
    assert sample_contract==real_contract
