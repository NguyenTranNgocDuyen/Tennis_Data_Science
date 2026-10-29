"""Incremental contributions -> common match store -> atomic analytical snapshot."""
from collections import defaultdict
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import hashlib

import pandas as pd

from src.data_collection.collect import collect,load_raw
from src.data_collection.common_reference import ensure_player_reference,load_draw_reference
from src.data_collection.raw_cache import atomic_json
from src.preprocessing import clean_matches,player_matches
from src.preprocessing.rapidapi_adapter import to_canonical,resolve_best_of,match_date
from src.preprocessing.common_semantics import api_semantics,MAIN_ROUNDS
from src.preprocessing.unified import IdentityResolver,SemanticError,source_to_common,merge_contributions,digest
from src.data_validation import load_schema,validate_frame
from src.analysis import build_tables
from src.analysis.reporting import write_table_contract


def overrides(path,kind):
    frame=pd.read_csv(path,dtype='string').fillna('')
    key='source_player_id' if kind=='player' else 'source_edition_id'
    result={}
    for row in frame.to_dict('records'):
        if not row.get('reason'):raise SemanticError('Every manual mapping must include its reason')
        pair=(row['provider'],row[key])
        if pair in result:raise SemanticError('Duplicate manual mapping')
        result[pair]=row
    return result


def load_unified(root,db,api_db,config,observer):
    project=json.loads((root/'config/project.json').read_text())
    source_schema=load_schema(root/'data/schemas/tennis_schema.json')
    schema=load_schema(root/'data/schemas/tennis_common_schema.json')
    aliases=json.loads((root/'config/tournament_aliases.json').read_text())
    format_rules=json.loads((root/'config/tennis_format_rules.json').read_text())
    references=load_draw_reference(root)
    player_overrides=overrides(root/config['player_overrides'],'player')
    edition_overrides=overrides(root/config['edition_overrides'],'edition')
    with observer.task('historical_collection'):
        collect(root,project,offline=True)
        historical=clean_matches(load_raw(root,project),source_schema,project).matches
        players_reference=ensure_player_reference(root,offline=True)
    api_rows=api_db.execute('SELECT * FROM matches ORDER BY match_date,stable_key').fetchall()
    code_root=Path(__file__).resolve().parents[1]
    code_paths=[Path(__file__).resolve(),code_root/'preprocessing/unified.py',code_root/'preprocessing/common_semantics.py',
                code_root/'preprocessing/rapidapi_adapter.py',code_root/'preprocessing/clean.py',code_root/'data_validation/validate.py']
    policy=digest({'config':config,'schema':schema,'aliases':aliases,'format':format_rules,
                   'semantic_code':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths},
                   'reference':references,'player_overrides':player_overrides,'edition_overrides':edition_overrides,
                   'player_reference':json.loads((root/'data/reference/github_players_manifest.json').read_text())['sha256']})
    old={r['match_id']:r['fingerprint'] for r in db.execute('SELECT match_id,fingerprint FROM common_matches')}
    source_old={(r['provider'],r['source_key']):r['fingerprint'] for r in db.execute('SELECT provider,source_key,fingerprint FROM source_records')}
    changes={'source_inserted':0,'source_updated':0,'source_unchanged':0}
    now=datetime.now(timezone.utc).isoformat()
    rejected=[];conflicts=[]
    with observer.task('common_normalization'):
        with db:
            db.execute('INSERT INTO loads(run_id,started_at,status) VALUES(?,?,?)',(observer.id,now,'normalizing'))
            resolver=IdentityResolver(db,historical,players_reference,aliases,player_overrides,edition_overrides)
            def apply(provider,key,original,provenance):
                fingerprint=digest([original,provenance,policy])
                previous=source_old.get((provider,key))
                if previous==fingerprint:
                    changes['source_unchanged']+=1;return
                changes['source_inserted' if previous is None else 'source_updated']+=1
                try:
                    shared,meta=source_to_common(original,provider,key,resolver,provenance)
                    # GitHub rows already passed vectorized source validation;
                    # mapping changes only checked identities/edition keys. Avoid
                    # tens of thousands of one-row pandas schema passes.
                    if provider!='github':
                        issues=validate_frame(pd.DataFrame([shared],columns=schema['required']).astype('string'),schema)
                        if issues.severity.eq('error').any():raise SemanticError('Required canonical field invalid: '+','.join(sorted(set(issues.loc[issues.severity.eq('error'),'field']))))
                        if len(issues):
                            meta['optional_validation_issues']=issues[['field','rule','severity']].to_dict('records')
                            corrected=clean_matches(pd.DataFrame([shared],columns=schema['required']).astype('string'),schema,project).matches
                            shared={k:None if pd.isna(v) else str(v) for k,v in corrected[schema['required']].iloc[0].items()}
                    status='ready';reason=None;payload=json.dumps(shared,ensure_ascii=False)
                except (SemanticError,ValueError,TypeError) as exc:
                    meta=provenance;status='quarantined';reason=str(exc);payload=None
                    rejected.append({'provider':provider,'source_key':key,'reason':reason})
                db.execute('''INSERT INTO source_records VALUES(?,?,?,?,?,?,?,?)
                  ON CONFLICT(provider,source_key) DO UPDATE SET fingerprint=excluded.fingerprint,row_json=excluded.row_json,provenance_json=excluded.provenance_json,status=excluded.status,reason=excluded.reason,loaded_at=excluded.loaded_at''',
                  (provider,key,fingerprint,payload,json.dumps(meta,ensure_ascii=False),status,reason,now))
            for row in historical[schema['required']].to_dict('records'):
                original={k:None if pd.isna(v) else str(v) for k,v in row.items()}
                key=original['tourney_id']+':'+original['match_num']
                apply('github',key,original,{'source_edition_id':original['tourney_id'],
                    'source_season':original['source_season'],'season_method':'source_file_season',
                    'match_date':None,'match_date_precision':'unknown','source_file':original['source_file'],'source_row':original['source_row']})
            for index,stored in enumerate(api_rows,start=2):
                row=json.loads(stored['payload_json']);tid=str(row['tournamentId'])
                override=edition_overrides.get(('rapidapi_tennis',tid),{})
                canonical=to_canonical(row,json.loads(stored['stats_json'] or '{}'),schema,stored['source_path'],index,format_rules)
                semantics=api_semantics(row,references,override)
                canonical['round']=semantics['round']
                canonical['draw_size']=str(semantics['draw_size']) if semantics['draw_size'] else None
                canonical['source_season']=str(semantics['season'])
                canonical['tourney_id']=f"{semantics['season']}-rapidapi-{tid}"
                # A December-only edition may belong to next season. Defer until
                # source evidence or explicit season mapping resolves it.
                start=str(row['tournament']['date'])[:10]
                if start[5:7]=='12' and not override.get('season') and int(start[:4])==semantics['season']:
                    canonical['source_season']=None
                best,method,reference=resolve_best_of(row,format_rules)
                if method=='verified_competition_rule' and semantics['season'] not in format_rules['valid_match_years']:
                    canonical['best_of']=None  # A cross-year season needs its own reviewed format rules.
                provenance={'source_edition_id':tid,'source_archive_id':stored['archive_id'],
                    'source_player_ids':[row['player1Id'],row['player2Id']],
                    'source_round_id':row['roundId'],'round_method':'reference_draw_slots' if row['roundId'] in {4,5,6,7} else 'round_lookup',
                    'round_reference':semantics['round_reference'],'source_match_date':row['date'],
                    'match_date':match_date(row),'match_date_precision':'day_utc',
                    'season_method':semantics['season_method'],'best_of_source':method,'best_of_reference':reference,
                    'stats_checked_at':stored['stats_checked_at'],'source_file':stored['source_path'],'stats_source_file':stored['stats_source_path']}
                apply('rapidapi_tennis',stored['stable_key'],canonical,provenance)
            # Rebuild the grouped view to detect source conflicts/remaps, while
            # writing only actual inserts/updates to the common fact table.
            groups=defaultdict(list)
            for record in db.execute("SELECT * FROM source_records WHERE status='ready'"):
                item=dict(record);meta=json.loads(item['provenance_json']);groups[meta['canonical_key']].append(item)
            new_ids=set();summary={'inserted':0,'updated':0,'unchanged':0,'removed_conflicting_or_remapped':0}
            for key,records in groups.items():
                try:
                    shared,meta=merge_contributions(records)
                except SemanticError as exc:
                    conflicts.extend({'canonical_key':key,'provider':r['provider'],'source_key':r['source_key'],'reason':str(exc)} for r in records)
                    continue
                match_id=shared['tourney_id']+':'+shared['match_num'];new_ids.add(match_id)
                # A fresh raw filename / source-row position is new evidence,
                # not a changed tennis result or statistic.
                fingerprint=digest([{k:v for k,v in shared.items() if k not in {'source_file','source_row'}},meta])
                if old.get(match_id)==fingerprint:summary['unchanged']+=1;continue
                summary['inserted' if match_id not in old else 'updated']+=1
                db.execute('INSERT INTO common_matches VALUES(?,?,?,?) ON CONFLICT(match_id) DO UPDATE SET row_json=excluded.row_json,provenance_json=excluded.provenance_json,fingerprint=excluded.fingerprint',
                    (match_id,json.dumps(shared,ensure_ascii=False),json.dumps(meta,ensure_ascii=False),fingerprint))
            removed=set(old)-new_ids
            for match_id in removed:db.execute('DELETE FROM common_matches WHERE match_id=?',(match_id,))
            summary['removed_conflicting_or_remapped']=len(removed)
            summary.update(changes)
            summary['conflicts']=len(conflicts)
            for conflict in conflicts:
                db.execute('INSERT INTO match_conflicts VALUES(?,?,?,?,?)',
                    (observer.id,conflict['canonical_key'],conflict['provider'],conflict['source_key'],conflict['reason']))
            summary['source_quarantined']=db.execute("SELECT COUNT(*) FROM source_records WHERE status='quarantined'").fetchone()[0]
            summary['total_matches']=len(new_ids)
            summary['source_api_records']=len(api_rows)
            summary['api_watermark']=max((r['last_seen_at'] for r in api_rows),default=None)
            summary['players_source_scoped']=db.execute("SELECT COUNT(*) FROM player_crosswalk WHERE method LIKE 'source_scoped%'").fetchone()[0]
            summary['editions_source_scoped']=db.execute("SELECT COUNT(*) FROM edition_crosswalk WHERE method='source_scoped_new_series'").fetchone()[0]
            db.execute('UPDATE loads SET status=?,summary_json=? WHERE run_id=?',('committed',json.dumps(summary),observer.id))
            db.execute('INSERT INTO load_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('policy_hash',policy))
            db.execute('INSERT INTO load_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_api_seen_at',summary['api_watermark']))
    if summary['source_quarantined']:
        observer.warning('validation','SEMANTIC_QUARANTINE',f"Có {summary['source_quarantined']} bản ghi nguồn chưa xác minh được ngữ nghĩa; chưa đưa vào dữ liệu chung.")
    if conflicts:
        observer.alert('validation','P2','COMMON_OUTCOME_CONFLICT','Có kết quả trận mâu thuẫn giữa các nguồn; đã giữ lại để kiểm tra.',['pipeline','data_quality','P2'])
    if summary['players_source_scoped']:
        observer.warning('validation','IDENTITY_REVIEW',f"Có {summary['players_source_scoped']} người chơi chưa liên kết chắc chắn; giữ ID theo nguồn và cần rà soát trước khi phân tích xuyên nguồn.")
    if summary['editions_source_scoped']:
        observer.warning('validation','EDITION_REVIEW',f"Có {summary['editions_source_scoped']} phiên bản giải mới chưa liên kết lịch sử; giữ riêng và cần rà soát trước khi so sánh theo chuỗi giải.")
    with observer.task('common_export'):
        current=root/config['output_directory']/'CURRENT.json'
        reusable=False
        if current.exists() and not any(summary[k] for k in ['inserted','updated','removed_conflicting_or_remapped','source_inserted','source_updated']):
            pointer=json.loads(current.read_text())
            previous=root/config['output_directory']/pointer['snapshot']/'manifest.json'
            reusable=previous.is_file() and json.loads(previous.read_text()).get('policy_hash')==policy
        if reusable:
            pointer['last_checked_at_utc']=now
            atomic_json(current,pointer)
            summary['snapshot_reused']=True
        else:
            pointer=publish_common(root,db,config,schema,project,observer,summary,conflicts,policy)
            summary['snapshot_reused']=False
    with db:db.execute('UPDATE loads SET status=?,snapshot=? WHERE run_id=?',('published',pointer['snapshot'],observer.id))
    return {**summary,'export':pointer}


def publish_common(root,db,config,schema,project,observer,summary,conflicts,policy):
    output=root/config['output_directory'];snapshots=output/'snapshots';snapshots.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.building-',dir=snapshots))
    try:
        records=db.execute('SELECT * FROM common_matches ORDER BY match_id').fetchall()
        if not records:raise SemanticError('No canonical matches remain; previous snapshot preserved. Inspect source_records and match_conflicts.')
        raw=pd.DataFrame([json.loads(r['row_json']) for r in records],columns=schema['required']).astype('string')
        cleaned=clean_matches(raw,schema,project)
        if len(cleaned.quarantine) or len(cleaned.matches)!=len(raw):raise SemanticError('Common fact store failed final invariant/schema validation')
        assert validate_frame(cleaned.matches,schema,allow_features=True).empty
        raw.to_csv(temp/'canonical_input.csv',index=False)
        cleaned.matches.to_csv(temp/'tennis_matches.csv',index=False)
        player_matches(cleaned.matches).to_csv(temp/'player_matches.csv',index=False)
        with observer.task('analysis'):
            tables=build_tables(cleaned.matches,raw,schema)
        (temp/'tables').mkdir()
        for name,table in tables.items():table.to_csv(temp/'tables'/f'{name}.csv',index=False)
        write_table_contract(temp/'tables/table_contract.json',tables)
        for name in ['players','player_crosswalk','editions','edition_crosswalk','source_records']:
            query=f'SELECT * FROM {name}'
            if name=='source_records':query="SELECT provider,source_key,status,reason,loaded_at,provenance_json FROM source_records"
            pd.read_sql_query(query,db).to_csv(temp/f'{name}.csv',index=False)
        pd.DataFrame(conflicts,columns=['canonical_key','provider','source_key','reason']).to_csv(temp/'conflicts.csv',index=False)
        provenance=[{'match_id':r['match_id'],**json.loads(r['provenance_json'])} for r in records]
        with (temp/'match_provenance.jsonl').open('w') as stream:
            for row in provenance:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        source_counts=pd.read_sql_query("SELECT provider,COUNT(*) AS records,SUM(status='ready') AS ready FROM source_records GROUP BY provider",db)
        source_counts.to_csv(temp/'coverage_by_source.csv',index=False)
        coverage=[]
        for record in db.execute("SELECT provider,row_json,provenance_json FROM source_records WHERE status='ready'"):
            value=json.loads(record['row_json']);meta=json.loads(record['provenance_json'])
            coverage.append({'provider':record['provider'],'season':int(value['source_season']),
                'tournament_reference_date':pd.to_datetime(value['tourney_date'],format='%Y%m%d').strftime('%Y-%m-%d'),
                'actual_match_date':meta.get('match_date')})
        covered=pd.DataFrame(coverage).groupby(['provider','season'],dropna=False).agg(
            source_records=('season','size'),first_tournament_reference_date=('tournament_reference_date','min'),
            last_tournament_reference_date=('tournament_reference_date','max'),
            first_known_match_date=('actual_match_date','min'),last_known_match_date=('actual_match_date','max')).reset_index()
        covered.to_csv(temp/'coverage_by_season.csv',index=False)
        import hashlib
        checksums={str(f.relative_to(temp)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(temp.rglob('*')) if f.is_file()}
        atomic_json(temp/'manifest.json',{'version':config['schema_version'],'operation_id':observer.id,'policy_hash':policy,
            'summary':summary,'flow':cleaned.flow,'n_tables':len(tables),'sha256':checksums,
            'limitations':['Coverage gap remains between end of historical snapshot and first API date; no backfill invented.',
                'Unknown pre-event ranking/minutes remain null. API actual dates are separate from tournament reference dates.',
                'Exact name+IOC linkage is recorded evidence, not proof; ambiguous identities remain distinct and flagged.']})
        destination=snapshots/observer.id;temp.rename(destination)
        pointer={'snapshot':str(destination.relative_to(output)),'n_matches':len(raw),'n_tables':len(tables),'schema_version':config['schema_version']}
        atomic_json(output/'CURRENT.json',pointer)
        return pointer
    except BaseException:
        if temp.exists():shutil.rmtree(temp)
        raise
