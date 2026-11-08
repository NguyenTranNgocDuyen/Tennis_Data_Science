from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib

import pandas as pd
import pytest

from scripts.run_pipeline import ROOT, make_sample, run


@pytest.fixture
def tmp_path():
    with TemporaryDirectory(prefix='pipeline-safety-', dir=ROOT) as path:
        yield Path(path)


def test_make_sample_writes_only_under_requested_output(tmp_path):
    raw = pd.DataFrame([
        {'source_file': 'a.csv', 'source_row': '1', 'source_season': '2020', 'surface': 'Hard',
         'score': '6-4 6-4', 'winner_rank': '10', 'loser_rank': '20'},
        {'source_file': 'a.csv', 'source_row': '2', 'source_season': '2020', 'surface': 'Clay',
         'score': '6-4 6-4', 'winner_rank': '11', 'loser_rank': '21'},
        {'source_file': 'b.csv', 'source_row': '3', 'source_season': '2021', 'surface': 'Hard',
         'score': '6-4 6-4', 'winner_rank': '12', 'loser_rank': '22'},
    ])
    result = SimpleNamespace(matches=raw[['source_file', 'source_row']].copy())
    config = {'sample_seed': 7, 'source_commit': 'fixture'}
    output = tmp_path/'isolated'
    original = {name: hashlib.sha256((ROOT/'data/sample'/name).read_bytes()).hexdigest()
                for name in ['tennis_sample.csv', 'sample_manifest.json']}

    make_sample(raw, result, config, output)

    assert (output/'data/sample/tennis_sample.csv').is_file()
    assert (output/'data/sample/sample_manifest.json').is_file()
    assert original == {name: hashlib.sha256((ROOT/'data/sample'/name).read_bytes()).hexdigest()
                        for name in original}


def test_pipeline_sample_run_preserves_repository_sample_files(tmp_path):
    original = {name: hashlib.sha256((ROOT/'data/sample'/name).read_bytes()).hexdigest()
                for name in ['tennis_sample.csv', 'sample_manifest.json']}
    output = tmp_path/'run-output'

    run(sample=True, output=output)

    assert (output/'reports/run_manifest.json').is_file()
    assert not (output/'data/sample').exists()
    assert original == {name: hashlib.sha256((ROOT/'data/sample'/name).read_bytes()).hexdigest()
                        for name in original}


def test_pipeline_refuses_nonempty_output_directory(tmp_path):
    output = tmp_path/'existing'
    output.mkdir()
    sentinel = output/'keep.txt'
    sentinel.write_text('preserve')

    with pytest.raises(FileExistsError):
        run(sample=True, output=output)

    assert sentinel.read_text() == 'preserve'
