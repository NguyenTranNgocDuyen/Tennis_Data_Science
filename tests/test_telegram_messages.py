import json
from datetime import datetime,timezone

from src.observability.messages import format_notification


def row(context=None,priority='P4',code='RUN_SUMMARY',message='',count=0):
    return {'id':42,'operation_id':'abc12345def67890','priority':priority,'stage':'pipeline',
            'code':code,'message':message,'context_json':json.dumps(context) if context else None,
            'created':datetime(2026,10,29,4,0,tzinfo=timezone.utc).timestamp(),'suppressed_count':count}


def test_live_summary_explains_data_and_followup_without_debug_dump():
    context={'pipeline':'api_batch','status':'succeeded_with_warnings','duration_seconds':12.3,
             'summary':{'start_date':'2026-10-22','end_date':'2026-10-28','inserted':70,'selected':70,
                        'stats_fetched':20,'stats_deferred':48,'export':{'n_matches':70,'n_tables':14}},
             'warnings':['Statistics deferred/unavailable in raw: 48; results are stored, coverage is partial.']}
    text=format_notification(row(context,'P3'))
    assert '70 trận mới' in text and '14 bảng' in text
    assert '48 trận chờ thống kê' in text and 'Bạn chưa cần thao tác' in text
    assert '11:00' in text and '29/10/2026' in text
    assert 'run=abc12345' in text and 'abc12345def67890' not in text
    assert '{' not in text and 'succeeded' not in text and 'stats_deferred' not in text


def test_all_quarantined_never_claims_analysis_success_or_no_action():
    context={'pipeline':'api_batch','status':'succeeded_with_warnings',
             'summary':{'selected':70,'inserted':70,'export':{'n_matches':0,'n_tables':0}},
             'warnings':['Quarantined 70/70 records (100.0%); inspect quarantine.csv and validation_issues.csv.']}
    text=format_notification(row(context,'P3'))
    assert 'CHƯA CÓ DỮ LIỆU' in text and '70/70 trận' in text
    assert 'Bạn cần kiểm tra' in text and 'Không cần thao tác' not in text
    assert 'THÀNH CÔNG' not in text


def test_export_only_summary_does_not_claim_new_api_collection():
    context={'pipeline':'api_batch','status':'succeeded','summary':{'export':{'n_matches':70,'n_tables':14}}}
    text=format_notification(row(context))
    assert 'XUẤT BẢNG' in text and '70 trận' in text
    assert 'trận mới' not in text and 'CẬP NHẬT TENNIS THÀNH CÔNG' not in text


def test_old_queued_json_is_presented_as_vietnamese_summary():
    legacy='Pipeline api_batch: succeeded\nsnapshot_export=succeeded\n'+json.dumps({'export':{'n_matches':70,'n_tables':14}})
    text=format_notification(row(message=legacy))
    assert '14 bảng' in text and 'snapshot_export' not in text and '{' not in text


def test_auth_failure_tells_user_what_to_fix():
    alert=row(priority='P2',code='API_AUTHORIZATION',message='sensitive technical text')
    alert['stage']='discovery'
    text=format_notification(alert)
    assert 'API key và gói đăng ký' in text and 'Lấy kết quả trận đấu' in text
    assert 'sensitive technical text' not in text


def test_deduplicated_digest_preserves_context_counts():
    context={'pipeline':'reproducibility','status':'succeeded','summary':{'verification':'passed'}}
    text=format_notification(row(context,count=7))
    assert 'khớp dữ liệu' in text and 'Đã gộp 7 cảnh báo lặp' in text


def test_long_summary_keeps_footer_and_stays_bounded():
    context={'pipeline':'api_batch','summary':{},'warnings':['unrecognized details '*1000]*20}
    text=format_notification(row(context,'P3'))
    assert len(text)<3900 and 'run=abc12345' in text
    assert 'unrecognized details' not in text


def test_unparseable_old_summary_does_not_invent_success():
    text=format_notification(row(message='malformed old payload'))
    assert 'Không đủ thông tin' in text and 'THÀNH CÔNG' not in text
