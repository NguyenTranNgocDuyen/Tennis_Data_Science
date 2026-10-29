"""Canonical identities and meanings for immutable GitHub and mutable API sources."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd

from .common_semantics import normalize_name,api_semantics


class SemanticError(ValueError): pass


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()


def nullable(value):
    return None if value is None or pd.isna(value) else str(value)


def canonical_score(score):
    import re
    if score is None or pd.isna(score):return None
    value=str(score).strip().replace('–','-').replace('—','-')
    value=re.sub(r'(?i)w\s*/\s*o','W/O',value)
    value=re.sub(r'(?i)\bret\.?','RET',value)
    value=re.sub(r'(?i)\bdef\.?','DEF',value)
    value=re.sub(r'\b(RET|DEF|W/O)(?:\s+\1)+',r'\1',value)
    return ' '.join(value.split())


DDL='''
CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY,name TEXT NOT NULL,dob TEXT);
CREATE TABLE IF NOT EXISTS player_crosswalk(provider TEXT,source_id TEXT,canonical_id INTEGER,method TEXT,evidence_json TEXT,PRIMARY KEY(provider,source_id));
CREATE TABLE IF NOT EXISTS editions(id TEXT PRIMARY KEY,series TEXT,season INTEGER,start_date TEXT,name TEXT,level TEXT,surface TEXT,draw_size INTEGER);
CREATE TABLE IF NOT EXISTS edition_crosswalk(provider TEXT,source_id TEXT,canonical_id TEXT,method TEXT,PRIMARY KEY(provider,source_id));
CREATE TABLE IF NOT EXISTS source_records(provider TEXT,source_key TEXT,fingerprint TEXT,row_json TEXT,provenance_json TEXT,status TEXT,reason TEXT,loaded_at TEXT,PRIMARY KEY(provider,source_key));
CREATE TABLE IF NOT EXISTS common_matches(match_id TEXT PRIMARY KEY,row_json TEXT,provenance_json TEXT,fingerprint TEXT);
CREATE TABLE IF NOT EXISTS loads(run_id TEXT PRIMARY KEY,started_at TEXT,status TEXT,summary_json TEXT,snapshot TEXT);
CREATE TABLE IF NOT EXISTS load_state(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS match_conflicts(run_id TEXT,canonical_key TEXT,provider TEXT,source_key TEXT,reason TEXT);
'''


def connect_unified(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=30);db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL');db.executescript(DDL)
    return db


class IdentityResolver:
    def __init__(self,db,historical,players_reference,aliases,player_overrides=None,edition_overrides=None):
        self.db=db;self.name_index=defaultdict(set);self.ref={};self.aliases={}
        self.historical_max_season=int(historical['source_season'].max()) if 'source_season' in historical and len(historical) else 0
        self.player_overrides=player_overrides or {};self.edition_overrides=edition_overrides or {}
        for group in aliases['series']:
            for name in group['aliases']:
                key=normalize_name(name)
                if key in self.aliases and self.aliases[key]['key']!=group['key']:raise SemanticError('Conflicting tournament alias')
                self.aliases[key]=group
        valid_dobs=pd.to_datetime(players_reference['dob'],format='%Y%m%d',errors='coerce')
        validated_reference=players_reference.copy()
        validated_reference['dob']=valid_dobs.dt.strftime('%Y%m%d').where(valid_dobs.notna(),None)
        for r in validated_reference.to_dict('records'):
            pid=int(r['player_id']);name=' '.join(str(r.get(k,'')) for k in ['name_first','name_last'] if pd.notna(r.get(k)))
            self.ref[pid]={'name':name,'dob':nullable(r.get('dob')),'ioc':nullable(r.get('ioc'))}
            self.name_index[(normalize_name(name),nullable(r.get('ioc')))].add(pid)
        for role in ['winner','loser']:
            for pid,name,ioc in historical[[role+'_id',role+'_name',role+'_ioc']].itertuples(index=False,name=None):
                pid=int(pid)
                self.ref.setdefault(pid,{'name':str(name),'dob':None,'ioc':nullable(ioc)})
                self.name_index[(normalize_name(name),nullable(ioc))].add(pid)
        # Merge duplicate source identities only when the same full-name/IOC key
        # also has one identical nonmissing birthdate across every candidate.
        parent={i:i for i in self.ref}
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for ids in self.name_index.values():
            birthdays={self.ref[i]['dob'] for i in ids}
            if len(ids)>1 and len(birthdays)==1 and None not in birthdays:
                roots=[find(i) for i in ids];target=min(roots)
                for i in roots:parent[i]=target
        self.github_ids={i:find(i) for i in parent}
        self.name_index={k:{self.github_ids[i] for i in ids} for k,ids in self.name_index.items()}
        self.review=[]
        self.player_cache={};self.edition_cache={}
        for row in db.execute('SELECT * FROM player_crosswalk'):
            self.player_cache[(row['provider'],row['source_id'])]=(row['canonical_id'],row['method'])
        for row in db.execute('SELECT * FROM edition_crosswalk'):
            self.edition_cache[(row['provider'],row['source_id'])]=row['canonical_id']

    def _save_player(self,provider,source_id,cid,name,dob,method,evidence):
        self.db.execute('INSERT INTO players VALUES(?,?,?) ON CONFLICT(id) DO NOTHING',(cid,name,dob))
        self.db.execute('INSERT INTO player_crosswalk VALUES(?,?,?,?,?) ON CONFLICT(provider,source_id) DO UPDATE SET canonical_id=excluded.canonical_id,method=excluded.method,evidence_json=excluded.evidence_json',
            (provider,str(source_id),cid,method,json.dumps(evidence,ensure_ascii=False)))
        self.player_cache[(provider,str(source_id))]=(cid,method)
        return cid,method

    def player(self,provider,source_id,name,ioc):
        source_id=str(source_id);key=(provider,source_id)
        override=self.player_overrides.get(key)
        if override:
            cid=int(override['canonical_player_id'])
            if cid not in self.ref:raise SemanticError('Player override target not present in GitHub reference')
            canonical=self.github_ids[cid];r=self.ref[canonical]
            return self._save_player(provider,source_id,canonical,r['name'],r['dob'],'reviewed_override',override)
        if provider=='github':
            cid=self.github_ids[int(source_id)];r=self.ref[cid]
            method='source_id' if cid==int(source_id) else 'duplicate_full_name_ioc_dob'
            return self._save_player(provider,source_id,cid,r['name'],r['dob'],method,{'source_player_id':source_id,'canonical_id':cid}) if self.player_cache.get(key)!=(cid,method) else self.player_cache[key]
        country=nullable(ioc)
        candidates=self.name_index.get((normalize_name(name),country),set()) if country not in {None,'UNK','N/A','U',''} else set()
        if len(candidates)==1:
            cid=next(iter(candidates));r=self.ref[cid]
            return self._save_player(provider,source_id,cid,r['name'],r['dob'],'unique_full_name_ioc',{'normalized_name':normalize_name(name),'ioc':nullable(ioc),'candidates':list(candidates)})
        # Never let identical numeric IDs from independent providers collide.
        cid=1_000_000_000+int(source_id)
        if cid in self.ref:raise SemanticError('Reserved source-only player ID range collided')
        method='source_scoped_ambiguous' if candidates else 'source_scoped_unmatched'
        self.review.append({'provider':provider,'source_player_id':source_id,'name':name,'ioc':nullable(ioc),
                            'canonical_player_id':cid,'status':method,'candidate_ids':','.join(map(str,sorted(candidates)))})
        return self._save_player(provider,source_id,cid,name,None,method,{'candidates':list(candidates)})

    def player_name(self,pid):
        return self.db.execute('SELECT name FROM players WHERE id=?',(pid,)).fetchone()[0]

    def edition(self,provider,source_id,name,season,start_date,level,surface,draw_size=None):
        key=(provider,str(source_id));override=self.edition_overrides.get(key,{})
        season=int(override.get('season') or season)
        alias=self.aliases.get(normalize_name(name))
        series=alias['key'] if alias else 'source_name_'+digest(normalize_name(name))[:16]
        canonical_name=alias['name'] if alias else name
        target=override.get('canonical_edition_id') or self.edition_cache.get(key)
        if target:
            row=self.db.execute('SELECT * FROM editions WHERE id=?',(target,)).fetchone()
            if not row:raise SemanticError('Edition override/crosswalk target missing')
            if row['season']!=season or abs((date.fromisoformat(row['start_date'])-date.fromisoformat(start_date)).days)>3:
                raise SemanticError('Edition season/date changed; explicit review required')
            if row['level']!=level or (row['surface'] and surface and row['surface']!=surface):
                raise SemanticError('Edition level/surface conflict')
            return dict(row)
        rows=self.db.execute('SELECT * FROM editions WHERE series=? AND season=? AND level=?',(series,season,level)).fetchall()
        close=[r for r in rows if abs((date.fromisoformat(r['start_date'])-date.fromisoformat(start_date)).days)<=3
               and (r['surface']==surface or not r['surface'] or not surface)]
        if len(close)>1:raise SemanticError('Ambiguous edition match; manual override required')
        if close:
            edition=dict(close[0]);method='series_season_date_surface'
        else:
            if provider!='github' and alias is None and season<=self.historical_max_season:
                raise SemanticError('Unresolved edition in a historical-overlap season; reviewed tournament alias/edition mapping required')
            eid=f'{season}-'+digest([series,start_date])[:16]
            edition={'id':eid,'series':series,'season':season,'start_date':start_date,'name':canonical_name,'level':level,'surface':surface,'draw_size':int(draw_size) if draw_size is not None and pd.notna(draw_size) else None}
            self.db.execute('INSERT INTO editions VALUES(:id,:series,:season,:start_date,:name,:level,:surface,:draw_size)',edition)
            method='explicit_alias' if alias else 'source_scoped_new_series' if provider!='github' else 'source_name_exact'
        self.db.execute('INSERT INTO edition_crosswalk VALUES(?,?,?,?)',(provider,str(source_id),edition['id'],method))
        self.edition_cache[key]=edition['id']
        return edition


def source_to_common(row,provider,source_key,resolver,provenance=None):
    d={k:nullable(v) for k,v in row.items()}
    player_methods={}
    for role in ['winner','loser']:
        pid,method=resolver.player(provider,d[role+'_id'],d[role+'_name'],d[role+'_ioc'])
        d[role+'_id']=str(pid);d[role+'_name']=resolver.player_name(pid);player_methods[role]=method
    if d['winner_id']==d['loser_id']:raise SemanticError('Identity resolution collapsed opponents to the same player')
    season=int(d['source_season']);start=pd.to_datetime(d['tourney_date'],format='%Y%m%d').date().isoformat()
    source_edition=(provenance or {}).get('source_edition_id',d['tourney_id'])
    edition=resolver.edition(provider,source_edition,d['tourney_name'],season,start,d['tourney_level'],d['surface'],d['draw_size'])
    d['tourney_id']=edition['id'];d['tourney_name']=edition['name'];d['source_season']=str(edition['season'])
    d['tourney_date']=date.fromisoformat(edition['start_date']).strftime('%Y%m%d')
    if edition['draw_size'] is not None:d['draw_size']=str(edition['draw_size'])
    d['score']=canonical_score(d['score'])
    key=digest([d['tourney_id'],d['round'],sorted([int(d['winner_id']),int(d['loser_id'])])])
    d['match_num']=str(int(key[:14],16))
    meta={**(provenance or {}),'provider':provider,'source_key':source_key,
          'canonical_key':key,'player_resolution':player_methods,'edition_id':edition['id']}
    return d,meta


def merge_contributions(contributions):
    """Conflict-aware coalescing; source-specific NULL never erases a known value."""
    rows=sorted(contributions,key=lambda r:(0 if r['provider']=='github' else 1,r['source_key']))
    primary=rows[0];value=json.loads(primary['row_json']);field_sources={}
    default_source=primary['provider']+':'+primary['source_key']
    conflicts=[]
    for other in rows[1:]:
        incoming=json.loads(other['row_json'])
        for key in ['winner_id','loser_id','score','best_of','round']:
            if value.get(key) is not None and incoming.get(key) is not None and str(value[key])!=str(incoming[key]):
                raise SemanticError('Conflicting match result/format across source records')
        for key,new in incoming.items():
            if key in {'source_file','source_row'}:continue
            if value.get(key) is None and new is not None:
                value[key]=new;field_sources[key]=other['provider']+':'+other['source_key']
            elif value.get(key) is not None and new is not None and str(value[key])!=str(new):
                conflicts.append({'field':key,'preferred':value[key],'alternative':new,'provider':other['provider']})
    provenance={'contributors':[{'provider':r['provider'],'source_key':r['source_key']} for r in rows],
                'default_field_source':default_source,
                'field_sources':field_sources,'optional_conflicts':conflicts}
    return value,provenance
