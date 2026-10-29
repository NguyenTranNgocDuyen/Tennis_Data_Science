"""Bounded, auditable HTTP client. Credentials never appear in URLs or logs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import requests


class APIError(RuntimeError):
    pass


class QuotaExceeded(APIError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RapidAPIClient:
    def __init__(self, key, config, db, raw_dir: Path, run_id, session=None, sleep=time.sleep):
        if not key or not key.strip():
            raise APIError("Missing RAPIDAPI_KEY. Configure the local .env file using .env.example.")
        if config['host'] != 'tennis-api-atp-wta-itf.p.rapidapi.com':
            raise APIError('Unexpected API host; credentials must only be sent to the documented provider.')
        self.key, self.config, self.db = key.strip(), config, db
        self.raw_dir, self.run_id = raw_dir, run_id
        self.session, self.sleep = session or requests.Session(), sleep
        self.calls = 0
        raw_dir.mkdir(parents=True, exist_ok=True)

    def available(self):
        today = datetime.now(timezone.utc).date().isoformat()
        row = self.db.execute('SELECT COUNT(*) FROM requests WHERE request_day=? AND is_network=1',(today,)).fetchone()
        return max(0, self.config['daily_request_budget']-row[0])

    def get(self, path: str, params: dict | None=None):
        if not path.startswith('/tennis/v2/') or '?' in path or '..' in path:
            raise APIError('Unexpected API path')
        params = params or {}
        for attempt in range(self.config['max_retries']+1):
            # Reserve before sending, including failures/retries, across all runs.
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                if not self.available():
                    raise QuotaExceeded('Local daily request budget reached; batch will not advance its watermark.')
                cur=self.db.execute('INSERT INTO requests(run_id,request_day,path,params,requested_at) VALUES(?,?,?,?,?)',
                                    (self.run_id,datetime.now(timezone.utc).date().isoformat(),path,json.dumps(params,sort_keys=True),utc_now()))
                request_id=cur.lastrowid
            self.calls+=1
            self.sleep(self.config['minimum_request_interval_seconds'])
            try:
                response=self.session.get('https://'+self.config['host']+path,params=params,
                    headers={'X-RapidAPI-Key':self.key,'X-RapidAPI-Host':self.config['host']},
                    timeout=self.config['timeout_seconds'],allow_redirects=False)
            except requests.RequestException:
                with self.db:
                    self.db.execute('UPDATE requests SET error=? WHERE id=?',('transport_error',request_id))
                if attempt < self.config['max_retries']:
                    self.sleep(2**attempt)
                    continue
                raise APIError('API transport failed after bounded retries; see request audit.') from None
            # Preserve response bytes and safe request metadata, never request headers.
            content=response.content.replace(self.key.encode(),b'[REDACTED]')
            raw_path=self.raw_dir/f'{request_id:08d}.json'
            # Durable raw is the recovery boundary, before parse/validation.
            import os
            with raw_path.open('xb') as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
            digest=hashlib.sha256(content).hexdigest()
            metadata={'path':path,'params':params,'status':response.status_code,'retrieved_at':utc_now(),
                      'sha256':digest,'request_id':request_id,'credentials_redacted':content!=response.content}
            from .raw_cache import atomic_json
            atomic_json(raw_path.with_suffix('.meta.json'),metadata)
            with self.db:
                self.db.execute('UPDATE requests SET status=?,raw_path=?,sha256=? WHERE id=?',
                                (response.status_code,str(raw_path),digest,request_id))
            observer=getattr(self,'observer',None)
            if observer: observer.event('raw.saved','discovery',request_id=request_id,path=path,http_status=response.status_code,sha256=digest,raw_path=str(raw_path))
            if response.status_code==429:
                raise QuotaExceeded('Provider returned HTTP 429; stop until quota/rate window resets. No watermark advanced.')
            if response.status_code in {500,502,503,504} and attempt < self.config['max_retries']:
                self.sleep(2**attempt)
                continue
            if response.status_code != 200:
                raise APIError(f'API HTTP {response.status_code}. Check subscription/key/endpoint; raw response saved locally.')
            try:
                payload=json.loads(content)
            except (ValueError,UnicodeDecodeError):
                raise APIError('API returned invalid JSON; response retained locally.') from None
            if not isinstance(payload,dict) or 'error' in payload:
                raise APIError('Unexpected API response envelope; refusing to mark batch successful.')
            return payload, str(raw_path)
        raise APIError('Retries exhausted')
