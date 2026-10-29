"""Export API-only snapshots through the existing B cleaning/statistics modules."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import pandas as pd

from src.preprocessing.rapidapi_adapter import to_canonical,resolve_best_of
from src.preprocessing import clean_matches, player_matches
from src.data_validation import validate_frame
from src.analysis import build_tables
from src.analysis.reporting import write_table_contract
from src.data_collection.common_reference import load_draw_reference


def export_api(db,root:Path,output:Path,config,schema,project_config,mode='live',observer=None):
    if observer: observer.start_task('normalization')
    rows=db.execute('SELECT * FROM matches ORDER BY match_date,stable_key').fetchall()
    canonical=[]
    provenance=[]
    rule_file=root/'config/tennis_format_rules.json'
    format_rules=json.loads(rule_file.read_text()) if rule_file.exists() else None
    semantic_reference=load_draw_reference(root)
    for index,stored in enumerate(rows,start=2):
        result=json.loads(stored['payload_json'])
        stats=json.loads(stored['stats_json'] or '{}')
        canonical.append(to_canonical(result,stats,schema,stored['source_path'],index,format_rules,semantic_reference))
        best_of,best_of_source,best_of_reference=resolve_best_of(result,format_rules)
        provenance.append({'stable_key':stored['stable_key'],'archive_id':stored['archive_id'],
            'provider':stored['provider'],'match_date_utc':stored['match_date'],
            'player_low_id':stored['player_low'],'player_high_id':stored['player_high'],
            'tournament_edition_id':stored['tournament_id'],'round_id':stored['round_id'],
            'raw_source':stored['source_path'],'stats_source':stored['stats_source_path'],
            'stats_checked_at':stored['stats_checked_at'],
            'best_of':best_of,'best_of_source':best_of_source,'best_of_reference':best_of_reference,
            'canonical_match_num':canonical[-1]['match_num']})
    raw=pd.DataFrame(canonical,columns=schema['required']).astype('string')
    if observer:
        observer.end_task('normalization',rows=len(raw));observer.start_task('validation')
    result=clean_matches(raw,schema,project_config)
    m=result.matches
    assert validate_frame(m,schema,allow_features=True).empty
    if observer:
        observer.end_task('validation',**result.flow);observer.quality(result.flow)
    output.mkdir(parents=True,exist_ok=True)
    snapshots=output/'snapshots'; snapshots.mkdir(exist_ok=True)
    # Publish CURRENT.json only after every snapshot artifact is complete.
    # A crash leaves old CURRENT valid; never advertise a half-written export.
    temp=Path(tempfile.mkdtemp(prefix='.building-',dir=snapshots))
    try:
        raw.to_csv(temp/'canonical_input.csv',index=False)
        m.to_csv(temp/'tennis_matches.csv',index=False)
        player_matches(m).to_csv(temp/'player_matches.csv',index=False)
        pd.DataFrame(provenance,columns=['stable_key','archive_id','provider','match_date_utc','player_low_id','player_high_id','tournament_edition_id','round_id','raw_source','stats_source','stats_checked_at','best_of','best_of_source','best_of_reference','canonical_match_num']).to_csv(temp/'provenance.csv',index=False)
        for name,frame in {'validation_issues':result.issues,'cleaning_actions':result.actions,
                           'quarantine':result.quarantine,'excluded_scope':result.excluded,'duplicates':result.duplicates}.items():
            frame.to_csv(temp/f'{name}.csv',index=False)
        tables={}
        if len(m):
            if observer: observer.start_task('analysis')
            tables=build_tables(m,raw,schema)
            if observer: observer.end_task('analysis',n_tables=len(tables))
            (temp/'tables').mkdir()
            for name,frame in tables.items():
                frame.to_csv(temp/'tables'/f'{name}.csv',index=False)
            write_table_contract(temp/'tables/table_contract.json',tables)
        status={
            'mode':mode,'provider':config['provider'],'exported_at_utc':datetime.now(timezone.utc).isoformat(),
            'config':config,'input_schema_version':project_config['schema_version'],
            'format_rules':format_rules,
            'derived_best_of_rows':sum(p['best_of_source']=='verified_competition_rule' for p in provenance),
            'flow':result.flow,'n_tables':len(tables),
            'historical_data_merged':False,'pre_match_rank_available':False,
            'limitations':['API-only results; provider IDs are not Sackmann IDs.',
                'Pre-event ranks and duration are not supplied by this adapter, so their metrics have no denominator.',
                'Missing best_of derives only from versioned verified 2026 competition rules; source is in provenance.csv. Outside rule scope remains missing.',
                'Statistics can be partial due to coverage and request budget; inspect provenance/stats_checked_at.',
                'Archive numeric match IDs are unstable; use stable_key.',
                'Demo mode uses synthetic test records, never real match results.']}
        hashes={str(f.relative_to(temp)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(temp.rglob('*')) if f.is_file()}
        status['sha256']=hashes
        (temp/'export_manifest.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
        import uuid
        name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
        destination=snapshots/name
        temp.rename(destination)
        pointer={'snapshot':str(destination.relative_to(output)),'mode':mode,'n_matches':len(m),'n_tables':len(tables)}
        pending=output/'CURRENT.json.tmp'
        pending.write_text(json.dumps(pointer,indent=2)+'\n')
        os.replace(pending,output/'CURRENT.json')
        return pointer
    except BaseException:
        if temp.exists():
            shutil.rmtree(temp)
        raise
