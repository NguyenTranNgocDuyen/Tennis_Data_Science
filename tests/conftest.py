import json
from pathlib import Path

import pandas as pd
import pytest

from src.data_validation import load_schema, validate_frame

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return json.loads((ROOT/'config/project.json').read_text())


@pytest.fixture
def schema():
    return load_schema(ROOT/'data/schemas/tennis_schema.json')


@pytest.fixture
def good_row(schema):
    d=pd.read_csv(ROOT/'data/sample/tennis_sample.csv',dtype='string')
    invalid=set(validate_frame(d,schema).row_index)
    return d.loc[[i for i in d.index if i not in invalid]].head(1).reset_index(drop=True)
