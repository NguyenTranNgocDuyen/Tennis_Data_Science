"""Offline synthetic replay client. Only used with separate demo storage."""
import json
from pathlib import Path
import shutil
import hashlib

from .rapidapi_client import APIError


class ReplayClient:
    def __init__(self,key,config,db,raw_dir,run_id):
        self.fixtures=Path(__file__).resolve().parents[2]/'tests/fixtures/rapidapi'
        self.raw_dir=raw_dir
        raw_dir.mkdir(parents=True,exist_ok=True)
        self.calls=0
        self.db,self.run_id=db,run_id

    def available(self):
        return 100-self.calls

    def get(self,path,params=None):
        params=params or {}
        if '/results/' in path:
            name=f"results_page_{params.get('pageNo',1)}.json"
        elif path.endswith('/stats'):
            sid=path.split('/')[-2]
            name=f'stats_{sid}.json'
        else:
            raise APIError('Replay route not available')
        source=self.fixtures/name
        if not source.exists():
            raise APIError(f'Missing synthetic replay fixture: {name}')
        self.calls+=1
        dest=self.raw_dir/f'{self.calls:04d}_{name}'
        shutil.copyfile(source,dest)
        from .rapidapi_client import utc_now
        with self.db:
            self.db.execute('INSERT INTO requests(run_id,request_day,path,params,requested_at,status,raw_path,sha256,is_network) VALUES(?,?,?,?,?,?,?,?,0)',
                (self.run_id,utc_now()[:10],path,json.dumps(params,sort_keys=True),utc_now(),200,str(dest),hashlib.sha256(dest.read_bytes()).hexdigest()))
        return json.loads(dest.read_text()),str(dest)
