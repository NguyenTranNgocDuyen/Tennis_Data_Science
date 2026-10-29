"""Single entry point: collect → validate → clean → features → tables → reports."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import pandas as pd
from src.data_collection import collect, load_raw
from src.data_validation import load_schema, validate_frame, summarize_validation
from src.preprocessing import clean_matches, player_matches
from src.analysis import build_tables
from src.analysis.reporting import write_reports, write_table_contract
from src.observability import Observer
from src.observability.runtime import load_env


def make_sample(raw, result, config):
    """Real source rows only; add two labeled exact duplicates for development."""
    retained = set(zip(result.matches.source_file,result.matches.source_row.astype('string')))
    valid = raw.loc[[tuple(r) in retained for r in raw[['source_file','source_row']].itertuples(index=False,name=None)]]
    # Include small groups and non-completed matches, then random records.
    selected = valid.groupby(['source_season','surface'],dropna=False).head(1)
    selected = pd.concat([selected, valid.loc[valid.score.str.contains('RET|W/O|DEF',na=False)].head(8),
                          valid.loc[valid.winner_rank.isna() | valid.loser_rank.isna()].head(5),
                          valid.sample(n=min(80,len(valid)),random_state=config['sample_seed'])]).drop_duplicates(['source_file','source_row'])
    sample = pd.concat([selected,selected.head(2)],ignore_index=True)
    sample.to_csv(ROOT/'data/sample/tennis_sample.csv',index=False)
    meta = {'seed':config['sample_seed'],'rows':len(sample),'base_rows':len(selected),
            'intentional_exact_duplicates':2,'artificial_value_errors':False,
            'description':'Real rows with original source_file/source_row, plus copies of first two rows. Not part of full analysis.',
            'source_commit':config['source_commit']}
    (ROOT/'data/sample/sample_manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')


def run(sample=False, offline=False, output: Path | None=None, observer=None):
    config = json.loads((ROOT/'config/project.json').read_text())
    schema = load_schema(ROOT/'data/schemas/tennis_schema.json')
    out = output.resolve() if output else (ROOT/'runs/sample' if sample else ROOT)
    manifest = None
    if observer: observer.start_task('historical_collection')
    if sample:
        raw = pd.read_csv(ROOT/'data/sample/tennis_sample.csv',dtype='string')
    else:
        manifest = collect(ROOT,config,offline=offline)
        raw = load_raw(ROOT,config)
    if observer:
        observer.end_task('historical_collection',rows=len(raw));observer.start_task('preprocessing')
    result = clean_matches(raw,schema,config)
    if result.matches.empty:
        raise ValueError('No analyzable matches remain after validation and scope filtering')
    post = validate_frame(result.matches,schema,allow_features=True)
    if len(post):
        raise ValueError('Post-cleaning validation failed: '+post.head().to_json())
    if observer:
        observer.end_task('preprocessing',**result.flow);observer.quality(result.flow);observer.start_task('analysis')
    tables = build_tables(result.matches,raw,schema)
    if observer:
        observer.end_task('analysis',n_tables=len(tables));observer.start_task('artifact_export')
    for directory in ['data/interim','data/processed','reports/tables']:
        (out/directory).mkdir(parents=True,exist_ok=True)
    for name, frame in {'validation_issues':result.issues, 'cleaning_actions':result.actions,
                        'excluded_scope':result.excluded, 'quarantine':result.quarantine,
                        'duplicates':result.duplicates}.items():
        frame.to_csv(out/f'data/interim/{name}.csv',index=False)
    result.matches.to_csv(out/'data/processed/tennis_matches.csv',index=False)
    player_matches(result.matches).to_csv(out/'data/processed/player_matches.csv',index=False)
    for name,table in tables.items():
        table.to_csv(out/f'reports/tables/{name}.csv',index=False)
    write_table_contract(out/'reports/tables/table_contract.json',tables)
    processed_contract = {'version':'1.0.0','primary_key':['match_id'],'source_schema':'data/schemas/tennis_schema.json',
                          'columns':[{'name':c,'dtype':str(result.matches[c].dtype),'nullable':bool(result.matches[c].isna().any())} for c in result.matches]}
    (out/'data/processed/processed_contract.json').write_text(json.dumps(processed_contract,indent=2)+'\n')
    write_reports(out,result,raw,schema,config,tables,manifest)
    files = sorted([*out.glob('data/interim/*.csv'),*out.glob('data/processed/*'),*out.glob('reports/tables/*'),
                    out/'reports/data_inventory.md',out/'reports/data_quality.md',out/'reports/eda_findings.md'])
    run_info = {'mode':'sample' if sample else 'real', 'config':config,
                'python':platform.python_version(),
                'packages':{p:importlib.metadata.version(p) for p in ['pandas','numpy','requests','jsonschema']},
                'flow':result.flow,'post_validation':summarize_validation(result.matches,post),
                'input_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
                                ([ROOT/'data/sample/tennis_sample.csv'] if sample else sorted((ROOT/'data/raw').glob('*.csv')))},
                'source_code_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
                                      sorted([*ROOT.glob('src/**/*.py'),*ROOT.glob('scripts/*.py'),ROOT/'data/schemas/tennis_schema.json'])},
                'outputs_sha256':{str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    (out/'reports/run_manifest.json').write_text(json.dumps(run_info,ensure_ascii=False,indent=2)+'\n')
    if not sample:
        make_sample(raw,result,config)
    print(json.dumps(result.flow,indent=2))
    print(f'Post-clean validation: {len(post)} issues; tables: {len(tables)}; output: {out}')
    if observer: observer.end_task('artifact_export')
    return result,tables


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true',help='Require and verify cached source files; never download')
    parser.add_argument('--sample',action='store_true',help='Run development sample into runs/sample, leaving real outputs intact')
    parser.add_argument('--output-dir',type=Path,help='Alternative output directory, useful for reproducibility checks')
    args=parser.parse_args()
    load_env(ROOT/'.env')
    observer=Observer(ROOT,'historical_pipeline','demo' if args.sample else 'live')
    try:
        result,tables=run(args.sample,args.offline,args.output_dir,observer)
        observer.finish({'flow':result.flow,'n_tables':len(tables)})
    except BaseException as exc:
        observer.finish(error=exc)
        raise
    finally: observer.close()
