"""Checksum-verified, run-scoped raw recovery. Never silently reuse stale live data."""
import hashlib
import json
from pathlib import Path

from .rapidapi_client import APIError, utc_now
from .api_store import canonical_json


class RawIntegrityError(APIError):
    pass


def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    import os,tempfile
    fd,name=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(obj,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)


def response_key(path,params):
    return canonical_json([path,params or {}])


def find_cached(db,run_id,path,params):
    """Search a recovery lineage, never an unrelated run or date window."""
    seen=set();current=run_id
    while current:
        if current in seen: raise RawIntegrityError('Raw recovery lineage cycle')
        seen.add(current)
        rows=db.execute('SELECT * FROM requests WHERE run_id=? AND path=? AND status=200 ORDER BY id DESC',(current,path)).fetchall()
        for row in rows:
            if json.loads(row['params'])==params:
                return dict(row)
        parent=db.execute('SELECT parent_run_id FROM batch_runs WHERE run_id=?',(current,)).fetchone()
        current=parent[0] if parent else None
    return None


def read_cached(record):
    file=Path(record['raw_path'])
    if not file.is_file(): raise RawIntegrityError('Raw integrity: recorded file is missing')
    content=file.read_bytes()
    if not record['sha256'] or hashlib.sha256(content).hexdigest()!=record['sha256']:
        raise RawIntegrityError('Raw checksum mismatch; refusing recovery from modified bytes')
    try: payload=json.loads(content)
    except (ValueError,UnicodeDecodeError): raise APIError('Stored HTTP 200 response is invalid JSON; original raw retained') from None
    if not isinstance(payload,dict) or 'error' in payload: raise APIError('Stored response has invalid/error envelope')
    return payload,str(file)


def write_raw_manifest(db,run_id,raw_dir,config):
    run=db.execute('SELECT * FROM batch_runs WHERE run_id=?',(run_id,)).fetchone()
    if not run: return
    requests=[dict(r) for r in db.execute('SELECT id,path,params,status,raw_path,sha256,error,is_network FROM requests WHERE run_id=? ORDER BY id',(run_id,))]
    cache=[dict(r) for r in db.execute('SELECT source_request_id,source_run_id,path,params,raw_path,sha256 FROM cache_hits WHERE run_id=? ORDER BY id',(run_id,))]
    import os
    for record in requests+cache:
        if record.get('raw_path'):
            record['file']=os.path.relpath(record['raw_path'],raw_dir)
    atomic_json(raw_dir/'run_manifest.json',{'version':'1.0.0','run':dict(run),'config':config,'requests':requests,'cache_hits':cache})


def import_bundle(raw_dir:Path,db):
    """Rebuild an offline index from raw + manifest, without the original SQLite."""
    raw_dir=raw_dir.resolve()
    manifest=json.loads((raw_dir/'run_manifest.json').read_text())
    run=manifest['run'];run_id=run['run_id']
    with db:
        db.execute('INSERT INTO batch_runs(run_id,mode,start_date,end_date,started_at,status,recovery_mode) VALUES(?,?,?,?,?,?,?)',
            (run_id,'imported',run['start_date'],run['end_date'],run['started_at'],run['status'],'raw_import'))
        for record in manifest['requests']+manifest.get('cache_hits',[]):
            if record.get('status',200)!=200 or not record.get('raw_path'): continue
            if 'file' not in record: raise RawIntegrityError('Raw bundle lacks portable file references; use a new manifest')
            file=(raw_dir/record['file']).resolve()
            if not file.is_relative_to(raw_dir.parent):
                raise RawIntegrityError('Raw bundle file escapes its raw root')
            cached={**record,'raw_path':str(file)}
            read_cached(cached)
            db.execute('INSERT INTO requests(run_id,request_day,path,params,requested_at,status,raw_path,sha256,is_network) VALUES(?,?,?,?,?,200,?,?,0)',
                (run_id,run['started_at'][:10],record['path'],record['params'],utc_now(),str(file),record['sha256']))
    return run_id,manifest['config']


class RecoveryClient:
    def __init__(self,source_db,source_run,db,run_id,delegate=None,offline=True,observer=None):
        self.source_db,self.source_run,self.db,self.run_id=source_db,source_run,db,run_id
        self.delegate,self.offline,self.observer=delegate,offline,observer
        self.calls=0;self.cache_hits=0
        self._delegate_instance=None

    def available(self):
        return self._delegate_instance.available() if self._delegate_instance else 100000

    def cached(self,path,params):
        return find_cached(self.source_db,self.source_run,path,params)

    def get(self,path,params=None):
        params=params or {}
        record=self.cached(path,params)
        if record:
            answer=read_cached(record)
            with self.db:
                self.db.execute('INSERT INTO cache_hits(run_id,source_run_id,source_request_id,path,params,raw_path,sha256,used_at) VALUES(?,?,?,?,?,?,?,?)',
                    (self.run_id,record['run_id'],record['id'],path,canonical_json(params),record['raw_path'],record['sha256'],utc_now()))
            self.cache_hits+=1
            if self.observer: self.observer.event('raw.cache_hit','recovery',source_run=record['run_id'],path=path,sha256=record['sha256'])
            return answer
        if self.offline:
            raise APIError('Required raw response not present in source run; offline replay will never call the API')
        if self._delegate_instance is None:
            self._delegate_instance=self.delegate() if callable(self.delegate) else self.delegate
        self.calls+=1
        return self._delegate_instance.get(path,params)
