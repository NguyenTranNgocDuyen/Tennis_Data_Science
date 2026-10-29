"""Incremental ingestion with full-page staging, optional enrichment and atomic upserts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import uuid

from .api_store import canonical_json
from .rapidapi_client import APIError, RapidAPIClient, utc_now
from src.preprocessing.rapidapi_adapter import (OutOfScope, RecordError, identity,
    stable_key, validate_result, validate_stats, match_date)

PROVIDER='rapidapi_tennis'


def result_digest(row):
    # Archive IDs are recycled; changing them alone is not a match correction.
    stable_content={k:v for k,v in row.items() if k not in {'id','matchId'}}
    return hashlib.sha256(canonical_json(stable_content).encode()).hexdigest()


def choose_window(db,config,today=None,reconcile=False):
    today=today or datetime.now(timezone.utc).date()
    end=today-timedelta(days=1)
    start=end-timedelta(days=29 if reconcile else config['lookback_days']-1)
    state=db.execute('SELECT last_success_date FROM sync_state WHERE provider=?',(PROVIDER,)).fetchone()
    if state and not reconcile:
        # Recover outages beyond lookback, while re-reading recent corrections.
        start=min(start,date.fromisoformat(state[0])+timedelta(days=1))
    return start,end


def ingest(db,config,raw_root: Path,key=None,start=None,end=None,client_factory=None,reconcile=False,
           observer=None,source_db=None,source_run=None,offline=False,run_id=None,mode='live'):
    if start is None or end is None:
        start,end=choose_window(db,config,reconcile=reconcile)
    if start>end:
        raise APIError('start date must not be after end date')
    if end>=datetime.now(timezone.utc).date():
        raise APIError('Results batches must end before today UTC; use completed-day windows.')
    run_id=run_id or uuid.uuid4().hex
    now=utc_now()
    with db:
        db.execute('INSERT INTO batch_runs(run_id,mode,start_date,end_date,started_at,status,parent_run_id,recovery_mode) VALUES(?,?,?,?,?,?,?,?)',
                   (run_id,mode,start.isoformat(),end.isoformat(),now,'collecting',source_run,'replay' if offline else 'resume' if source_run else 'live'))
    counts={'pages':0,'selected':0,'out_of_scope':0,'inserted':0,'updated':0,'unchanged':0,'stats_fetched':0}
    current_stage='discovery'
    try:
        if observer: observer.start_task(current_stage)
        factory=client_factory or RapidAPIClient
        def new_client():
            client=factory(key,config,db,raw_root/run_id,run_id)
            client.observer=observer
            return client
        if source_run:
            from .raw_cache import RecoveryClient
            client=RecoveryClient(source_db or db,source_run,db,run_id,new_client,offline,observer)
        else:
            client=new_client()
        staged={}
        page=1
        seen_pages=set()
        while True:
            path=f'/tennis/v2/atp/results/{start.isoformat()}/{end.isoformat()}'
            payload,source=client.get(path,{'pageNo':page,'pageSize':config['page_size'],'filter':'PlayerGroup:singles'})
            rows=payload.get('data')
            has_next=payload.get('hasNextPage')
            if not isinstance(rows,list) or type(has_next) is not bool or any(not isinstance(row,dict) for row in rows):
                raise APIError('Results envelope changed: expected data array and boolean hasNextPage.')
            if payload.get('pageNo',payload.get('page',page))!=page:
                raise APIError('Provider returned a different page number')
            fingerprint=hashlib.sha256(canonical_json(rows).encode()).hexdigest()
            if rows and fingerprint in seen_pages:
                raise APIError('Repeated results page; refusing incomplete pagination')
            seen_pages.add(fingerprint)
            counts['pages']+=1
            if not rows and has_next:
                raise APIError('Empty page with hasNextPage=true')
            for row in rows:
                try:
                    validate_result(row,config)
                    if not start.isoformat()<=match_date(row)<=end.isoformat():
                        raise RecordError('Result outside requested UTC date window')
                except OutOfScope:
                    counts['out_of_scope']+=1
                    continue
                except RecordError as exc:
                    with db:
                        db.execute('INSERT INTO rejected_records(run_id,source_path,reason,payload_json) VALUES(?,?,?,?)',
                                   (run_id,source,str(exc),canonical_json(row)))
                    raise APIError('Invalid result retained in rejected_records; no match upserts or watermark committed.') from None
                sid=stable_key(row)
                if sid in staged and canonical_json(staged[sid]['row'])!=canonical_json(row):
                    raise APIError('Conflicting result content across pages for same stable match key')
                staged[sid]={'row':row,'source':source,'stats':None,'stats_path':None,'stats_checked':None}
            if not has_next:
                break
            page+=1
        counts['selected']=len(staged)
        if observer:
            observer.end_task(current_stage,pages=counts['pages'],selected=len(staged))
            current_stage='enrichment';observer.start_task(current_stage)
        # Enrichment is a queue ordered by least recently checked. It cannot
        # consume quota until every discovery page has completed successfully.
        candidates=[]
        for sid,item in staged.items():
            old=db.execute('SELECT stats_checked_at,payload_hash,stats_json FROM matches WHERE provider=? AND stable_key=?',(PROVIDER,sid)).fetchone()
            checked=old['stats_checked_at'] if old else None
            if item['row']['result_type']=='walkover':
                continue
            if checked and old['payload_hash']==result_digest(item['row']):
                age=datetime.now(timezone.utc)-datetime.fromisoformat(checked)
                refresh=config['stats_refresh_days'] if json.loads(old['stats_json'] or '{}') else config['stats_empty_retry_days']
                if age<timedelta(days=refresh):
                    continue
            candidates.append((checked or '',sid,item))
        for _,sid,item in sorted(candidates,key=lambda x:(x[0],x[1]))[:config['max_stats_requests_per_run']]:
            # Composite key works in either player order and survives archive-ID recycling.
            stats_path=f'/tennis/v2/matches/{sid}/stats';stats_params={'type':'atp','source':'game'}
            cached=bool(source_run and client.cached(stats_path,stats_params))
            if not cached and client.available()<=0:
                continue
            if offline and not client.cached(stats_path,stats_params):
                counts['stats_missing_raw']=counts.get('stats_missing_raw',0)+1
                continue
            payload,source=client.get(stats_path,stats_params)
            try:
                item['stats']=validate_stats(payload,item['row'])
            except RecordError as exc:
                raise APIError('Invalid statistics identity/shape; retained raw response, no batch committed.') from None
            item['stats_path'],item['stats_checked']=source,utc_now()
            counts['stats_fetched']+=1
        finished=utc_now()
        counts['cache_hits']=getattr(client,'cache_hits',0)
        counts['stats_candidates']=len(candidates)
        counts['stats_deferred']=len(candidates)-counts['stats_fetched']
        if observer and counts['stats_deferred']:
            observer.warning('enrichment','STATS_BACKLOG',f"Statistics deferred/unavailable in raw: {counts['stats_deferred']}; results are stored, coverage is partial.")
        if observer:
            observer.end_task(current_stage,stats_fetched=counts['stats_fetched'])
            current_stage='database_commit';observer.start_task(current_stage)
        # One transaction: complete selected match set and contiguous watermark.
        with db:
            for sid,item in staged.items():
                row=item['row']; a,b,tid,rnd=identity(row)
                content=canonical_json(row)
                digest=result_digest(row)
                old=db.execute('SELECT * FROM matches WHERE provider=? AND stable_key=?',(PROVIDER,sid)).fetchone()
                stats=item['stats']
                # An empty stats response does not erase previously acquired data.
                previous=json.loads(old['stats_json']) if old and old['stats_json'] else {}
                core_changed=bool(old and old['payload_hash']!=digest)
                if core_changed:
                    previous={}  # Do not carry stale stats through a corrected result.
                merged=stats if stats else previous
                archive_id=str(row.get('matchId',row.get('id','')))
                changed=not old or old['payload_hash']!=digest or canonical_json(merged)!=canonical_json(previous)
                counts['inserted' if not old else 'updated' if changed else 'unchanged']+=1
                db.execute('''INSERT INTO matches VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(provider,stable_key) DO UPDATE SET
                  archive_id=excluded.archive_id,match_date=excluded.match_date,payload_json=excluded.payload_json,
                  payload_hash=excluded.payload_hash,stats_json=excluded.stats_json,stats_checked_at=excluded.stats_checked_at,
                  source_path=excluded.source_path,stats_source_path=excluded.stats_source_path,
                  last_seen_at=excluded.last_seen_at,changed_at=excluded.changed_at,run_id=excluded.run_id''',
                  (PROVIDER,sid,archive_id,match_date(row),str(tid),rnd,min(a,b),max(a,b),content,digest,
                   canonical_json(merged),item['stats_checked'] or (old['stats_checked_at'] if old and not core_changed else None),
                   item['source'],item['stats_path'] or (old['stats_source_path'] if old and not core_changed else None),
                   old['first_seen_at'] if old else finished,finished,
                   finished if changed else old['changed_at'],run_id))
            state=db.execute('SELECT last_success_date FROM sync_state WHERE provider=?',(PROVIDER,)).fetchone()
            # Explicit backfills can be disjoint. Never skip an uncollected gap.
            if not state or start<=date.fromisoformat(state[0])+timedelta(days=1):
                watermark=max(end.isoformat(),state[0] if state else end.isoformat())
                db.execute('INSERT INTO sync_state VALUES(?,?,?) ON CONFLICT(provider) DO UPDATE SET last_success_date=excluded.last_success_date,run_id=excluded.run_id',
                           (PROVIDER,watermark,run_id))
            db.execute('UPDATE batch_runs SET status=?,finished_at=?,summary_json=? WHERE run_id=?',
                       ('succeeded',finished,canonical_json(counts),run_id))
        if observer: observer.end_task(current_stage,**counts)
        return {'run_id':run_id,'start_date':start.isoformat(),'end_date':end.isoformat(),**counts}
    except Exception as exc:
        if observer: observer.fail_task(current_stage,exc)
        # Public messages are constructed, never include response headers or key.
        safe=str(exc) if isinstance(exc,(APIError,RecordError)) else type(exc).__name__
        with db:
            db.execute('UPDATE batch_runs SET status=?,finished_at=?,error=? WHERE run_id=?',('failed',utc_now(),safe,run_id))
        raise APIError(safe) from None
    finally:
        from .raw_cache import write_raw_manifest
        write_raw_manifest(db,run_id,raw_root/run_id,config)
