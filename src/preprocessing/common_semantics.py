"""Source-neutral field meanings; reference evidence is explicit and persisted."""
import math
import re
import unicodedata


ROUNDS={9:'QF',10:'SF',12:'F',8:'RR'}
MAIN_ROUNDS={4,5,6,7,8,9,10,12}


def normalize_name(value):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(value)).casefold() if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def bracket_size(payload,edition_id):
    data=payload.get('data',payload)
    if not isinstance(data,dict) or not isinstance(data.get('singles'),list): return None
    rows=data['singles'];positions={}
    for r in rows:
        if not isinstance(r,dict):continue
        if str(r.get('tournamentId',(r.get('tournament') or {}).get('id')))!=str(edition_id):return None
        if r.get('roundId')==4:
            position=r.get('draw')
            if isinstance(position,int) and position>0:positions[position]=1
    n=len(positions)
    if n<4 or set(positions)!=set(range(1,n+1)) or n&(n-1):return None
    # fullBracket=true must contain complete opening slots plus QF/SF/final slots.
    for rnd,expected in [(9,4),(10,2),(12,1)]:
        actual={r.get('draw') for r in rows if r.get('roundId')==rnd}
        if actual!=set(range(1,expected+1)):return None
    return n*2


def common_round(round_id,draw_size=None):
    if round_id in ROUNDS:return ROUNDS[round_id]
    if round_id not in {4,5,6,7} or not draw_size:return None
    try:size=int(draw_size)
    except (ValueError,TypeError):return None
    if size<8 or size&(size-1):return None
    remaining=size//(2**(round_id-4))
    # Ordinal First..Fourth are used only BEFORE quarterfinal. An impossible
    # combination stays missing rather than relabeling a semifinal as R16.
    return f'R{remaining}' if remaining>=16 else None


def api_semantics(row,reference,edition_override=None):
    t=row['tournament'];tid=str(t['id'])
    info=reference.get(tid,{})
    size=info.get('draw_size')
    rnd=common_round(row['roundId'],size)
    season=(edition_override or {}).get('season')
    if not season:
        season=int(str(row['date'])[:4])
    return {'round':rnd,'draw_size':size,'season':int(season),
            'season_method':'explicit_override' if edition_override and edition_override.get('season') else 'match_calendar_year',
            'round_reference':info.get('raw_path'),'series_reference':info.get('info_raw_path')}
