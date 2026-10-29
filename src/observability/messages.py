"""Vietnamese Telegram presentation; machine diagnostics stay in logs/outbox."""
from datetime import datetime, date
import json
import re
from zoneinfo import ZoneInfo

STAGES={
    'discovery':'Lấy kết quả trận đấu','enrichment':'Bổ sung thống kê trận',
    'database_commit':'Lưu dữ liệu','normalization':'Chuẩn hóa dữ liệu',
    'validation':'Kiểm tra chất lượng','analysis':'Phân tích thống kê',
    'snapshot_export':'Xuất bảng kết quả','artifact_export':'Xuất báo cáo',
    'historical_collection':'Đọc dữ liệu lịch sử','preprocessing':'Làm sạch dữ liệu',
    'verify_checksums_and_rebuild':'Kiểm tra khả năng tái lập',
    'notebook_execution':'Chạy notebook','notebook_publish':'Lưu notebook',
    'telegram':'Kết nối Telegram','pipeline':'Toàn bộ quy trình'}
STAGES.update({'reference':'Kiểm tra bảng tham chiếu','common_normalization':'Chuẩn hóa dữ liệu chung',
               'common_export':'Xuất bộ dữ liệu chung','api_reconciliation':'Đối soát dữ liệu API'})
PRIORITIES={'P1':'Khẩn cấp','P2':'Cần xử lý','P3':'Cần lưu ý','P4':'Thông tin'}


def period(start,end):
    try:
        a,b=date.fromisoformat(start),date.fromisoformat(end)
        return a.strftime('%d/%m/%Y') if a==b else f"{a:%d/%m} – {b:%d/%m/%Y}"
    except (ValueError,TypeError): return None


def translate_warning(message):
    if message.startswith(('Có ','Một số phiên bản')):return message
    m=re.search(r'Quarantined (\d+)/(\d+)',message)
    if m: return f"{int(m[1]):,}/{int(m[2]):,} trận được tạm giữ vì chưa đạt kiểm tra dữ liệu."
    m=re.search(r'(?:deferred/unavailable in raw:|raw:) (\d+)',message)
    if m: return f"{int(m[1]):,} trận chưa có thống kê chi tiết."
    m=re.search(r'Invalid optional cells set missing: (\d+)',message)
    if m: return f"{int(m[1]):,} giá trị không hợp lệ đã được chuyển thành dữ liệu thiếu."
    return 'Có cảnh báo cần xem chi tiết trong log.'


def legacy_context(row):
    """Render already-queued old summaries without forwarding JSON to the user."""
    text=row['message']
    first=text.splitlines()[0] if text else ''
    m=re.match(r'Pipeline ([\w_]+): (\w+)',first)
    if row['code']=='RUN_SUMMARY' and m:
        lines=text.splitlines();summary={};warnings=[]
        for index,line in enumerate(lines):
            if line.startswith('{'):
                try:
                    summary=json.loads(line);warnings=lines[index+1:];break
                except ValueError: pass
        return {'pipeline':m[1],'status':m[2],'summary':summary,'warnings':warnings}
    return {}


def summary_body(context,priority):
    summary=context.get('summary') or {}
    if not isinstance(summary,dict): summary={}
    pipeline=context.get('pipeline','api_batch')
    warnings=context.get('warnings') or []
    export=summary.get('export') or {}
    flow=summary.get('flow') or {}
    if not isinstance(export,dict): export={}
    if not isinstance(flow,dict): flow={}
    rows=export.get('n_matches',flow.get('processed_rows'))
    blocked=rows==0 and (summary.get('selected',0)>0 or flow.get('raw_rows',0)>0)
    attention=bool(warnings or priority=='P3' or summary.get('stats_deferred',0))
    if blocked: title='⛔ CHƯA CÓ DỮ LIỆU ĐỦ ĐIỀU KIỆN PHÂN TÍCH'
    elif pipeline=='unified_weekly': title='⚠️ ĐÃ ĐỒNG BỘ DỮ LIỆU CHUNG — CÓ LƯU Ý' if attention else '✅ ĐÃ ĐỒNG BỘ DỮ LIỆU CHUNG'
    elif pipeline=='reproducibility': title='✅ KIỂM TRA TÁI LẬP THÀNH CÔNG'
    elif pipeline=='member_b_notebook': title='✅ NOTEBOOK ĐÃ CHẠY XONG'
    elif pipeline=='historical_pipeline': title='⚠️ DỮ LIỆU LỊCH SỬ ĐÃ XỬ LÝ — CÓ LƯU Ý' if attention else '✅ DỮ LIỆU LỊCH SỬ ĐÃ XỬ LÝ XONG'
    elif 'selected' not in summary and export: title='⚠️ ĐÃ XUẤT BẢNG — CÓ LƯU Ý' if attention else '✅ ĐÃ XUẤT BẢNG PHÂN TÍCH TENNIS'
    else: title='⚠️ CẬP NHẬT TENNIS XONG — CÓ LƯU Ý' if attention else '✅ CẬP NHẬT TENNIS THÀNH CÔNG'
    lines=[title]
    window=period(summary.get('start_date'),summary.get('end_date'))
    if window: lines.extend(['',f'Dữ liệu: {window}'])
    metrics=[]
    if summary.get('inserted'): metrics.append(f"{summary['inserted']:,} trận mới")
    if summary.get('updated'): metrics.append(f"{summary['updated']:,} trận được cập nhật")
    if summary.get('unchanged'): metrics.append(f"{summary['unchanged']:,} trận không thay đổi")
    if metrics: lines.append('• '+', '.join(metrics)+'.')
    if pipeline=='unified_weekly' and 'source_api_records' in summary:
        lines.append(f"• Đã đối chiếu {summary['source_api_records']:,} bản ghi API với nền dữ liệu lịch sử.")
    if rows is not None:
        tables=export.get('n_tables',summary.get('n_tables'))
        lines.append(f"• Đủ điều kiện phân tích: {rows:,} trận"+(f"; đã tạo {tables:,} bảng." if tables is not None else '.'))
    if summary.get('stats_fetched'):
        lines.append(f"• Đã lấy thêm thống kê chi tiết cho {summary['stats_fetched']:,} trận.")
    pending=summary.get('stats_deferred',0)
    if pending:
        lines.extend(['',f"Còn {pending:,} trận chờ thống kê chi tiết."])
    if pipeline=='reproducibility' and summary.get('verification')=='passed':
        lines.append('Kết quả chạy lại khớp dữ liệu và bảng đã lưu.')
    if pipeline=='member_b_notebook':
        if 'executed_cells' in summary: lines.append(f"Đã chạy {summary['executed_cells']}/{summary.get('code_cells',summary['executed_cells'])} ô lệnh, {summary.get('errors',0)} lỗi.")
        if 'image_outputs' in summary: lines.append(f"Đã tạo {summary['image_outputs']} hình phân tích.")
    for message in warnings[:3]:
        if pending and ('Statistics deferred' in message or 'coverage is partial' in message): continue
        lines.append('• '+translate_warning(message))
    if len(warnings)>3: lines.append(f'• Còn {len(warnings)-3} lưu ý khác trong log.')
    if blocked:
        lines.extend(['','Bạn cần kiểm tra: các dòng bị tạm giữ và quy tắc/schema trước khi dùng kết quả.'])
    elif any('Quarantined ' in w for w in warnings):
        lines.extend(['','Bạn cần kiểm tra các dòng bị tạm giữ; các trận đạt kiểm tra vẫn dùng được.'])
    elif pending:
        lines.extend(['','Bạn chưa cần thao tác. Hệ thống sẽ tiếp tục bổ sung ở các lượt thu thập sau.'])
    elif attention:
        lines.extend(['','Kết quả đã được lưu. Xem log nếu cần kiểm tra các lưu ý trên.'])
    else: lines.extend(['','Không cần thao tác thêm.'])
    duration=context.get('duration_seconds')
    if isinstance(duration,(int,float)): lines.append(f'Thời gian chạy: {duration:.1f} giây.')
    return '\n'.join(lines)


def failure_body(row):
    code=row['code'];stage=STAGES.get(row['stage'],'Xử lý dữ liệu')
    title='🚨 CẦN XỬ LÝ NGAY' if row['priority']=='P1' else '⛔ TÁC VỤ CHƯA HOÀN TẤT'
    advice={
        'API_AUTHORIZATION':('API chưa cho phép truy cập.','Kiểm tra API key và gói đăng ký trong RapidAPI.'),
        'API_QUOTA':('Đã chạm giới hạn gọi API.','Chờ hạn mức được đặt lại. Tránh chạy lại liên tục.'),
        'RAW_INTEGRITY':('File raw không khớp bản gốc hoặc đang thiếu.','Kiểm tra bản sao lưu raw; không sửa checksum để bỏ qua lỗi.'),
        'QUARANTINE_RATIO':('Nhiều trận chưa đạt kiểm tra chất lượng.','Kiểm tra các dòng bị tạm giữ và quy tắc/schema.'),
    }
    reason,action=advice.get(code,('Có lỗi trong công đoạn xử lý.','Tra log theo mã bên dưới để xem nguyên nhân và cách chạy lại.'))
    return f'{title}\n\nCông đoạn: {stage}.\n{reason}\n\nBạn cần làm: {action}'


def format_notification(row):
    """One compact plain-text message. No raw JSON, stack trace or long IDs."""
    try: context=json.loads(row.get('context_json') or '{}')
    except (ValueError,TypeError): context={}
    if not context: context=legacy_context(row)
    if row['code']=='RUN_SUMMARY' and context: text=summary_body(context,row['priority'])
    elif row['code']=='RUN_SUMMARY': text='ℹ️ THÔNG BÁO KẾT QUẢ CŨ\n\nKhông đủ thông tin để tóm tắt an toàn. Tra log theo mã bên dưới để xem kết quả.'
    elif row['code']=='CONFIGURATION_TEST': text='✅ BOT ĐÃ KẾT NỐI\n\nThông báo pipeline sẽ được gửi vào chat riêng này.\nĐây là tin kiểm tra, không phải lượt thu thập dữ liệu mới.'
    else: text=failure_body(row)
    if row.get('suppressed_count'):
        text+=f"\n\nĐã gộp {row['suppressed_count']} cảnh báo lặp cùng loại."
    stamp=datetime.fromtimestamp(row['created'],ZoneInfo('Asia/Ho_Chi_Minh'))
    priority=row['priority']
    category='KetQua' if row['code']=='RUN_SUMMARY' else 'API' if row['code'] in {'API_AUTHORIZATION','API_QUOTA'} else 'DuLieu' if row['code'] in {'RAW_INTEGRITY','QUARANTINE_RATIO'} else 'KiemTra' if row['code']=='CONFIGURATION_TEST' else 'SuCo'
    # Short token is sufficient for rg; full correlation ID stays in JSONL/outbox.
    footer=f"\n\n🕒 {stamp:%H:%M · %d/%m/%Y} (giờ VN)\n#{priority} #{category} · {PRIORITIES.get(priority,'Thông báo')}\nMã tra cứu: run={str(row['operation_id'])[:8]} · tin={row['id']}"
    # Keep the correlation footer even if a future summary becomes too long.
    return text[:3200]+footer
