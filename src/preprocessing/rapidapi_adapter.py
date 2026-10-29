"""Provider-specific interpretation. API IDs never share Sackmann's namespace."""
from __future__ import annotations

from datetime import date
import hashlib
import re

import pandas as pd

from src.data_collection.api_store import canonical_json
from .common_semantics import common_round,MAIN_ROUNDS


class RecordError(ValueError):
    pass


class OutOfScope(RecordError):
    pass


def integer(value, name):
    if isinstance(value,bool) or value is None or not re.fullmatch(r'\d+',str(value)):
        raise RecordError(f'Missing/invalid {name}')
    return int(value)


def identity(row):
    p1,p2=row.get('player1') or {},row.get('player2') or {}
    t=row.get('tournament') or {}
    a=integer(row.get('player1Id',p1.get('id')),'player1Id')
    b=integer(row.get('player2Id',p2.get('id')),'player2Id')
    tid=integer(row.get('tournamentId',t.get('id')),'tournamentId')
    rnd=integer(row.get('roundId'),'roundId')
    if min(a,b,tid)<=0:
        raise RecordError('Nonpositive player/tournament ID')
    for actual,obj,field in [(a,p1,'player1.id'),(b,p2,'player2.id'),(tid,t,'tournament.id')]:
        if obj.get('id') is not None and integer(obj['id'],field)!=actual:
            raise RecordError('Conflicting nested and top-level identity')
    if a==b:
        raise RecordError('Identical players')
    if any(p.get('members') or '/' in str(p.get('name','')) for p in (p1,p2)):
        raise OutOfScope('Doubles result')
    return a,b,tid,rnd


def stable_key(row):
    a,b,tid,rnd=identity(row)
    return f'{min(a,b)}-{max(a,b)}-{tid}-{rnd}'


def check_scope(row,config):
    _,_,_,rnd=identity(row)
    t=row.get('tournament') or {}
    level=integer(t.get('rankId',(t.get('rank') or {}).get('id')),'tournament.rankId')
    if level not in config['included_rank_ids'] or rnd not in MAIN_ROUNDS:
        raise OutOfScope('Outside main-draw tour scope')
    for pattern in config['excluded_tournament_patterns']:
        if re.search(pattern,str(t.get('name',''))):
            raise OutOfScope('Excluded named tournament')


def match_date(row):
    value=row.get('date')
    if not isinstance(value,str):
        raise RecordError('Missing match date')
    try:
        stamp=pd.Timestamp(value)
        if pd.isna(stamp):
            raise ValueError()
        if stamp.tzinfo is not None:
            stamp=stamp.tz_convert('UTC')
        return stamp.date().isoformat()
    except (ValueError,TypeError,OverflowError):
        raise RecordError('Invalid match date') from None


def validate_result(row,config):
    check_scope(row,config)
    a,b,_,_=identity(row)
    match_date(row)
    for player in ('player1','player2'):
        if not isinstance(row.get(player),dict) or not row[player].get('name'):
            raise RecordError('Missing player name')
    if not (row.get('tournament') or {}).get('name'):
        raise RecordError('Missing tournament name')
    if row.get('match_winner') is not None and integer(row['match_winner'],'match_winner')!=a:
        raise RecordError('Results winner conflicts with player1 orientation')
    if row.get('result_type') not in {'completed','retired','walkover','default'}:
        raise RecordError('Unknown result_type; do not guess completion')
    if not isinstance(row.get('result'),str) or not row['result'].strip():
        raise RecordError('Missing result score')


def validate_stats(payload,row):
    """Reject swapped/foreign stats; return maps by actual player ID, never position."""
    data=payload.get('data',payload)
    if data=={}:
        return {}
    if not isinstance(data,dict):
        raise RecordError('Invalid statistics envelope')
    a,b,_,_=identity(row)
    output={}
    for index in (1,2):
        block=data.get(f'player{index}Stats')
        if block is None:
            continue
        if not isinstance(block,dict):
            raise RecordError('Invalid player statistics')
        pid=integer(block.get(f'player{index}Id',block.get('playerId')),'statistics player ID')
        if pid not in {a,b} or str(pid) in output:
            raise RecordError('Statistics refer to unexpected/duplicate player')
        output[str(pid)]=block
    if not output and data:
        raise RecordError('Unrecognized nonempty statistics payload')
    return output


def resolve_best_of(row,rules=None):
    if row.get('best_of') is not None:
        return row['best_of'],'api',None
    if not rules:
        return None,'missing',None
    try:
        a,b,tid,rnd=identity(row)
        year=date.fromisoformat(match_date(row)).year
        tournament=row.get('tournament') or {}
        level=str(integer(tournament.get('rankId',(tournament.get('rank') or {}).get('id')),'rankId'))
    except RecordError:
        return None,'missing',None
    if year not in rules['valid_match_years'] or rnd<=3:
        return None,'missing',None
    if any(re.search(pattern,str(tournament.get('name',''))) for pattern in rules['excluded_tournament_patterns']):
        return None,'missing',None
    value=rules['best_of_by_rank_id'].get(level)
    if value is None:
        return None,'missing',None
    return value,'verified_competition_rule',rules['sources']['grand_slam' if level=='4' else 'atp']


def to_canonical(row, stats, schema, source_path, source_row=2,format_rules=None,semantic_reference=None):
    """Map into B's lexical 52-column contract; unknown fields stay missing.

    No current rank is substituted for pre-event rank. Missing best_of can use
    explicitly versioned competition rules; other unknown core values quarantine.
    """
    a,b,tid,rnd=identity(row)
    key=stable_key(row)
    t=row['tournament']
    d={c:None for c in schema['required']}
    # Season comes from tournament start year. Do not invent a start date from
    # a match date; missing start dates are quarantined by the shared validator.
    start=t.get('date') or t.get('startDate')
    parsed=pd.to_datetime(start,utc=True,errors='coerce') if start else pd.NaT
    season=parsed.year if pd.notna(parsed) else date.fromisoformat(match_date(row)).year
    d.update(tourney_id=f'{season}-rapidapi-{tid}',tourney_name=t['name'],
             tourney_date=parsed.strftime('%Y%m%d') if pd.notna(parsed) else None,
             tourney_level={2:'A',3:'M',4:'G',7:'F'}.get(int(t.get('rankId',(t.get('rank') or {}).get('id')))),
             match_num=str(int(hashlib.sha256(key.encode()).hexdigest()[:15],16)),
             best_of=resolve_best_of(row,format_rules)[0],round=common_round(rnd,(semantic_reference or {}).get(str(tid),{}).get('draw_size')),
             source_season=season,source_file=source_path,source_row=source_row)
    court=(t.get('court') or {})
    d['surface']={1:'Hard',2:'Clay',3:'Hard',4:'Carpet',5:'Grass'}.get(t.get('courtId',court.get('id')))
    if not d['surface']:
        name=str(court.get('name','')).casefold()
        d['surface']={'hard':'Hard','i.hard':'Hard','indoor hard':'Hard','clay':'Clay','grass':'Grass','carpet':'Carpet'}.get(name)
    status=row['result_type']
    score=row['result'].strip()
    marker={'retired':'RET','walkover':'W/O','default':'DEF'}.get(status)
    if marker and not re.search({'RET':r'\bRET\b','W/O':r'W\s*/\s*O','DEF':r'\bDEF\b'}[marker],score,re.I):
        score+=' '+marker
    d['score']=score
    mapping={'ace':'aces','df':'doubleFaults','svpt':'firstServeOf','1stIn':'firstServe',
             '1stWon':'winningOnFirstServe','2ndWon':'winningOnSecondServe',
             'bpSaved':'breakPointSavedGm','bpFaced':'breakPointFacedGm'}
    for role,prefix,player,pid in [('winner','w',row['player1'],a),('loser','l',row['player2'],b)]:
        d[f'{role}_id']=pid
        d[f'{role}_name']=player['name']
        d[f'{role}_ioc']=player.get('countryAcr')
        d[f'{role}_seed']=player.get('seed')
        block=(stats or {}).get(str(pid),{})
        for stat,api_field in mapping.items():
            d[f'{prefix}_{stat}']=block.get(api_field)
    # Duration, pre-match rank/age and service-game totals are deliberately null
    # unless a future documented source-specific adapter supplies them.
    return {c:None if v is None else str(v) for c,v in d.items()}
