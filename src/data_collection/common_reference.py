"""Rare-changing metadata cache, sharing the existing HTTP audit/quota guard."""
from pathlib import Path
import hashlib
import json
import os
import uuid

import pandas as pd
import requests

from .rapidapi_client import RapidAPIClient,APIError,utc_now
from .raw_cache import atomic_json,read_cached
from src.preprocessing.common_semantics import bracket_size


def load_draw_reference(root):
    path=root/'data/reference/api_editions.json'
    reference=json.loads(path.read_text()) if path.exists() else {}
    for tid,item in reference.items():
        payload,_=read_cached({'raw_path':item['raw_path'],'sha256':item['sha256']})
        if bracket_size(payload,tid)!=item.get('draw_size'):
            raise APIError('Draw reference integrity mismatch: declared capacity differs from raw bracket')
    return reference


def ensure_player_reference(root,offline=False):
    dest=root/'data/reference/github_players.csv';manifest=dest.with_name('github_players_manifest.json')
    cfg=json.loads((root/'config/project.json').read_text())
    url=f"https://raw.githubusercontent.com/{cfg['source_repository']}/{cfg['source_commit']}/atp/atp_players.csv"
    if dest.exists() and manifest.exists():
        meta=json.loads(manifest.read_text())
        if meta['url']!=url or hashlib.sha256(dest.read_bytes()).hexdigest()!=meta['sha256']:
            raise APIError('Player reference checksum/config mismatch')
        return pd.read_csv(dest,dtype='string')
    if offline:raise APIError('Player reference missing; initialize once online before offline common-schema load')
    response=requests.get(url,timeout=60);response.raise_for_status()
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(response.content)
    frame=pd.read_csv(dest,dtype='string')
    required={'player_id','name_first','name_last','dob','ioc'}
    if not required.issubset(frame.columns):raise APIError('Unexpected player reference schema')
    atomic_json(manifest,{'url':url,'source_commit':cfg['source_commit'],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'rows':len(frame),'license':'CC BY-NC-SA 4.0','downloaded_at_utc':utc_now()})
    return frame


def cached_get(db,path,params,client):
    for row in db.execute('SELECT * FROM requests WHERE path=? AND status=200 ORDER BY id DESC',(path,)).fetchall():
        if json.loads(row['params'])==params:
            return read_cached(dict(row))
    if client is None or client.available()<=0:raise APIError('No quota/key for missing reference metadata')
    return client.get(path,params)


def refresh_draw_reference(root,db,config,limit=6,offline=False,observer=None):
    path=root/'data/reference/api_editions.json'
    reference=load_draw_reference(root)
    rows=[json.loads(r[0]) for r in db.execute('SELECT payload_json FROM matches')]
    events={str(r['tournamentId']):r['tournament'] for r in rows}
    run_id='reference-'+uuid.uuid4().hex
    client=None
    if not offline and os.environ.get('RAPIDAPI_KEY'):
        client=RapidAPIClient(os.environ['RAPIDAPI_KEY'],config,db,root/config['raw_directory']/run_id,run_id)
        client.observer=observer
    start=client.calls if client else 0;missing=[]
    for tid,t in sorted(events.items()):
        existing=reference.get(tid)
        if existing and existing.get('draw_size'):
            raw=Path(existing['raw_path'])
            if hashlib.sha256(raw.read_bytes()).hexdigest()!=existing['sha256']:raise APIError('Draw reference checksum mismatch')
            continue
        try:
            if client and client.calls-start>=limit:
                missing.append(tid);continue
            year=int(t['date'][:4])
            payload,raw=cached_get(db,f'/tennis/v2/tournament/atp/{tid}/{year}/draws',{'fullBracket':'true'},client)
            size=bracket_size(payload,tid)
            if size is None:
                missing.append(tid);continue
            reference[tid]={'draw_size':size,'method':'complete_main_draw_slots','raw_path':raw,
                'sha256':hashlib.sha256(Path(raw).read_bytes()).hexdigest(),'source_date':t['date'],'source_name':t['name'],'cached_at_utc':utc_now()}
            atomic_json(path,reference)
        except APIError:
            missing.append(tid)
            if observer:observer.warning('reference','REFERENCE_DEFERRED','Một số phiên bản giải chưa có bảng nhánh đấu đã xác minh; các vòng đầu sẽ được giữ để kiểm tra.')
    return reference,{'events':len(events),'cached':len(reference),'missing':missing,'network_requests':client.calls if client else 0}
