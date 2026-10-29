"""Vietnamese reports generated from verified tables, never hand-entered metrics."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .statistics import TABLE_NOTES, summary


def md_table(df: pd.DataFrame, digits=3) -> str:
    def fmt(v):
        if pd.isna(v):
            return "—"
        if isinstance(v, float):
            return f"{v:,.{digits}f}"
        return str(v).replace("|", "\\|").replace("\n", " ")
    return "| " + " | ".join(map(str,df.columns)) + " |\n| " + " | ".join(["---"]*len(df.columns)) + " |\n" + "\n".join("| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False,name=None))


def write_reports(out: Path, result, raw: pd.DataFrame, schema: dict, config: dict, tables: dict, manifest: dict | None):
    reports = out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    m = result.matches
    s = summary(m)
    scope_issues = result.issues.loc[~result.issues.row_index.isin(result.excluded.index)]
    counts = result.issues.groupby(["severity","field","rule"]).size().reset_index(name="n_issues")
    scope_counts = scope_issues.groupby(["severity","field","rule"]).size().reset_index(name="n_issues")
    post = __import__('src.data_validation',fromlist=['validate_frame']).validate_frame(m,schema,allow_features=True)
    raw_empty = raw.apply(lambda col: col.astype('string').str.strip().replace('',pd.NA).isna()).sum().sum()
    clean_empty = m[list(schema['required'])].isna().sum().sum()
    quality = f"""# Chất lượng dữ liệu trước và sau xử lý

Báo cáo được tạo tự động từ pipeline A và B. Các số dòng dưới đây là kết quả chạy thực tế, không phải số dự kiến.

## Đối soát số dòng

{md_table(pd.DataFrame(list(result.flow.items()),columns=['metric','value']),0)}

Đẳng thức kiểm tra: raw = ngoài phạm vi + cách ly + bản sao bỏ + processed. Bản ghi bị loại vẫn được lưu trong `data/interim/`; không sửa file gốc.

## Kiểm định đầu vào

{md_table(counts,0) if len(counts) else 'Không phát hiện vi phạm quy tắc.'}

Số vi phạm không bằng số ô sửa: một ô có thể vi phạm nhiều quy tắc; một thống kê giao bóng mâu thuẫn làm cả khối của người chơi đó được đặt thiếu.

Các vi phạm trong phạm vi phân tích:

{md_table(scope_counts,0) if len(scope_counts) else 'Không phát hiện vi phạm trong phạm vi.'}

## Quy tắc xử lý

- Cột bắt buộc thiếu toàn bộ: dừng pipeline. Trường định danh, tên, mùa, ngày, vòng, thể thức sai hoặc thiếu: cách ly dòng; người thắng và thua không được cùng ID.
- Lọc mã A M G F và loại giải đồng đội, Olympic, Next Gen bằng các biểu thức tên trong cấu hình. Không bao gồm Challenger, vòng loại và đơn nữ.
- Chuẩn hóa khoảng trắng; parse số nullable; số đếm phải nguyên không âm; rank và minutes phải dương; tuổi trong [10,80], chiều cao trong [120,250] cm. Đây là ngưỡng kiểm định miền, không phải ngưỡng cắt thống kê.
- Bản sao hoàn toàn xét các cột nguồn và mùa, bỏ qua vị trí file/dòng: giữ bản đầu. Cùng `tourney_id:match_num` nhưng khác nội dung: cách ly tất cả bản còn lại, không chọn tùy ý.
- Metadata tùy chọn sai: đặt thiếu và ghi `cleaning_actions.csv`. Thống kê giao bóng không nhất quán: đặt thiếu toàn bộ 9 trường của riêng người chơi đó.
- Không điền trung bình, không gán rank thiếu thành hạng thấp, không thay thời lượng thiếu bằng 0. Surface thiếu thành nhóm Unknown ở đặc trưng, giá trị gốc vẫn thiếu.
- Thời lượng <20 hoặc >360 phút được gắn cờ kiểm tra, giữ trong kết quả chính. Bảng độ nhạy loại các giá trị này để so sánh. Không winsorize và không xóa ngoại lệ chỉ vì vượt IQR.
- Mẫu số bằng 0 tạo tỷ lệ thiếu. Phân tích upset chỉ dùng trận hoàn tất với hai rank có mặt và khác nhau. Phân tích giao bóng dùng từng cặp tử số/mẫu số hợp lệ.

## Kiểm định sau xử lý

Có {len(post):,} vi phạm schema/ngữ nghĩa còn lại; ID trận duy nhất: {m.match_id.is_unique}. Có {int(m.duration_review_flag.sum()):,} trận được gắn cờ thời lượng. Các giá trị cực đoan còn lại cần được đối chiếu nguồn trước khi diễn giải riêng.

Tổng ô thiếu trong 52 cột đầu vào: {int(raw_empty):,}/{len(raw)*len(schema['required']):,} trước lọc; {int(clean_empty):,}/{len(m)*len(schema['required']):,} sau xử lý. Hai quần thể khác nhau, không dùng chênh lệch này để tuyên bố pipeline đã cải thiện tỷ lệ thiếu. Pipeline có thể tăng tỷ lệ thiếu vì loại giá trị sai.

Chi tiết theo cột: `reports/tables/quality_by_field.csv`; theo mùa: `reports/tables/missingness_by_season.csv`. Bằng chứng từng dòng: `data/interim/validation_issues.csv`, `cleaning_actions.csv`, `quarantine.csv`, `duplicates.csv`, `excluded_scope.csv`.

## Hạn chế còn lại

Kiểm định tự động không chứng minh toàn bộ bản ghi đúng hoặc nguồn thu thập đầy đủ. RET, DEF, W/O giữ lại cho kiểm kê nhưng loại khỏi so sánh thi đấu hoàn tất. Nhãn completed chỉ dựa vào cú pháp tỷ số và marker, không xác minh số set bằng luật tennis. Thiếu thống kê có thể có hệ thống theo giải/mùa, nên kết quả trên phần có dữ liệu có thể lệch. Chưa đối chiếu từng trận với bảng điểm chính thức.
"""
    (reports/'data_quality.md').write_text(quality,encoding='utf-8')
    season = tables['season_summary']
    surface = tables['surface_summary']
    duration = tables['duration_by_surface_format']
    serve = tables['serve_by_surface']
    ranked = m.loc[m.is_completed & m.rank_pair_available]
    rank_unknown = int(m.is_completed.sum())-len(ranked)
    overall_upset = float(ranked.is_upset.mean()) if len(ranked) else float('nan')
    c2020 = season.loc[season.season.eq(2020),'n_matches']
    c2019 = season.loc[season.season.eq(2019),'n_matches']
    trend_note = ''
    if len(c2020) and len(c2019):
        a,b=int(c2020.iloc[0]),int(c2019.iloc[0])
        trend_note=f'Mùa 2020 có {a:,} trận so với {b:,} của 2019, giảm {(1-a/b):.1%}. Dữ liệu chứng minh sự giảm số trận trong nguồn; nguyên nhân và tác động của từng thay đổi lịch giải cần nguồn bổ sung, không thể suy ra chỉ từ bảng này.'
    coverage = season[['season','n_completed','n_duration']].copy()
    coverage['duration_coverage'] = coverage.n_duration / coverage.n_completed
    lowest = coverage.loc[coverage.duration_coverage.idxmin()]
    coverage_note = f"Mùa có độ phủ thời lượng thấp nhất là {int(lowest.season)}: {int(lowest.n_duration):,}/{int(lowest.n_completed):,} trận hoàn tất ({lowest.duration_coverage:.1%}). Vì vậy xu hướng median thời lượng theo mùa chỉ phản ánh phần có dữ liệu và không thể coi là thay đổi toàn tour."
    comparison = duration.merge(tables['duration_sensitivity'],on=['surface_group','best_of'],suffixes=['_main','_sensitivity'])
    comparison = comparison[['surface_group','best_of','n_duration_main','n_duration_sensitivity','mean_minutes_main','mean_minutes_sensitivity','median_minutes_main','median_minutes_sensitivity']]
    suspicious = m.loc[m.is_completed & m.best_of.eq(3) & m.minutes.gt(600),['match_id','tourney_name','winner_name','loser_name','score','minutes']]
    rank_counts = tables['rank_group_performance']
    top10 = rank_counts.loc[rank_counts.rank_group.eq('Top 10')]
    rank_note = ''
    if len(top10):
        t=top10.iloc[0]
        rank_note=f"Nhóm Top 10 thắng {int(t.wins):,}/{int(t.n_appearances):,} lượt thi đấu hoàn tất ({t.win_rate:.1%}). Đây là thống kê theo thứ hạng trước giải của từng lượt, không phải chỉ thống kê rank của người thắng."
    ace = serve.loc[serve.metric.eq('ace_rate')].copy()
    ace_note = ''
    if len(ace):
        hi,lo=ace.loc[ace.rate.idxmax()],ace.loc[ace.rate.idxmin()]
        ace_note=f"Tỷ lệ ace gộp cao nhất trên {hi.surface_group}: {int(hi.numerator):,}/{int(hi.denominator):,} = {hi.rate:.2%}; thấp nhất trên {lo.surface_group}: {lo.rate:.2%}. Chênh lệch {(hi.rate-lo.rate)*100:.2f} điểm phần trăm. Đây là tương quan mô tả, còn khác biệt người chơi, giải và thể thức."
    findings = f"""# Phân tích khám phá tennis giai đoạn {config['start_season']} đến {config['end_season']}

## Phạm vi và câu hỏi nghiên cứu

Phân tích {len(m):,} bản ghi đơn nam cấp tour theo phạm vi A M G F đã lọc giải đồng đội, Olympic và Next Gen. Nguồn do Jeff Sackmann / Tennis Abstract biên soạn, tải từ bản lưu trữ được ghim commit. Mục tiêu là mô tả cơ cấu mặt sân, khác biệt thời lượng và giao bóng, quan hệ thứ hạng với kết quả, xu hướng số trận theo mùa. Không xây dựng mô hình dự đoán trong phần A và B.

Đơn vị gốc là một trận. Khi phân tích người chơi, mỗi trận tạo hai lượt người chơi. `season` lấy từ tên file; `tournament_start_year` là năm lịch của ngày giải. Không gọi tourney_date là ngày diễn ra trận và không dùng match_num để suy ra trình tự thời gian.

## Kết quả chính

Có {s['n_completed']:,} trận hoàn tất trên {s['n_matches']:,} bản ghi ({s['n_completed']/s['n_matches']:.2%}). Có {len(ranked):,} trận đủ hai rank khác nhau; {int(ranked.is_upset.sum()):,} trận người có thứ hạng thấp hơn thắng, tỷ lệ {overall_upset:.2%}. {rank_unknown:,} trận hoàn tất bị loại khỏi mẫu số upset vì thiếu rank hoặc hai rank bằng nhau. Upset ở đây không xét tỷ lệ cược và không có nghĩa là kết quả khó dự đoán theo mọi thước đo.

{rank_note}

{ace_note}

{trend_note}

{coverage_note}

## Cơ cấu dữ liệu và xu hướng mùa giải

{md_table(season)}

{md_table(surface)}

Mỗi tỷ lệ upset có mẫu số riêng `n_ranked_completed`; median_minutes chỉ dùng `n_duration` trận hoàn tất có thời lượng. Các tỷ lệ được lưu dạng 0–1 trong CSV, khi viết báo cáo mới đổi sang phần trăm. Số giải dùng tourney_id và chỉ tính các giải có bản ghi được giữ lại, không phải kiểm kê lịch ATP chính thức.

## So sánh thời lượng theo mặt sân và thể thức

{md_table(duration)}

So sánh chính phải nằm trong cùng best_of; gộp 3 set và 5 set sẽ trộn ảnh hưởng thể thức với mặt sân. Bảng `duration_sensitivity.csv` cho kết quả khi bỏ cờ thời lượng cực đoan. `season_surface.csv` hỗ trợ xem tiếp thay đổi theo mùa. Các thống kê không điều chỉnh trình độ người chơi, vòng đấu, giải hay thời tiết nên không kết luận mặt sân gây ra chênh lệch.

Đối chiếu kết quả chính và độ nhạy:

{md_table(comparison)}

Các thời lượng trên 600 phút của trận 3 set cần kiểm chứng nguồn trước khi dùng riêng hoặc dùng mean làm kết luận:

{md_table(suspicious) if len(suspicious) else 'Không có trong lần chạy này.'}

Không suy đoán giá trị sửa từ các con số này. Danh sách đầy đủ cờ kiểm tra nằm ở `duration_review.csv`; cờ <20 phút thường là bỏ cuộc sớm, vì vậy không tự xem mọi cờ là lỗi dữ liệu. Median và so sánh độ nhạy được ưu tiên cho diễn giải thời lượng.

## Phân phối thứ hạng và hiệu suất theo nhóm

{md_table(rank_counts)}

Nhóm Top 10, 11–50, 51–100, 101+ thay đổi theo rank trước mỗi giải; Unknown không bị ép vào 101+. Cùng một người có thể xuất hiện ở nhiều nhóm qua thời gian. Tổng lượt bằng hai lần số trận hoàn tất, tổng thắng bằng số trận hoàn tất. Danh sách người chơi trong `player_summary.csv` nối bằng ID, không bằng tên. Số thắng tuyệt đối chịu ảnh hưởng số lần tham dự.

## Giao bóng và mẫu số

{md_table(serve.loc[serve.metric.isin(['ace_rate','first_serve_win_rate','second_serve_win_rate'])])}

Tỷ lệ ace = tổng ace / tổng điểm giao bóng trên các lượt có đủ cặp số liệu. Tỷ lệ thắng giao bóng hai dùng `svpt - 1stIn`, bao gồm điểm lỗi kép. Không lấy trung bình đơn giản tỷ lệ từng trận. Từng metric có n_appearances và denominator riêng; thiếu một chỉ số không làm mất toàn bộ trận khỏi các phân tích không liên quan.

## Phân phối và giới hạn diễn giải

`numeric_summary.csv` chứa count, mean, std, min, p25, median, p75, p95, max cho các biến số gốc. `score_status.csv` cho phân phối tình trạng trận; `missingness_by_season.csv` cho sự thiếu dữ liệu theo mùa. Notebook B vẽ phân phối thời lượng và thể hiện các so sánh chính trực tiếp từ bảng đầu ra.

Đây là thống kê mô tả của dữ liệu quan sát đã chọn, không phải mẫu ngẫu nhiên của mọi trận tennis. Các trận lặp lại cùng người chơi và cùng giải có phụ thuộc; không diễn giải p-value độc lập hay khoảng tin cậy nhị thức đơn giản. Không dùng chênh lệch làm bằng chứng nhân quả. So sánh theo năm bị ảnh hưởng lịch giải, số vòng, phạm vi nguồn và độ đầy đủ thống kê. Không suy rộng sang WTA, Challenger, vòng loại hoặc giải đồng đội.

Nguồn thiếu một số thống kê; không điền giá trị có thể bịa ra hiệu suất. Cấu trúc winner/loser đã chứa kết quả: nếu C hoặc nhóm mở rộng sang dự đoán thì không dùng các cột hậu trận, phải tái thiết kế hướng người chơi và chia tập theo thời gian. Chưa có mô hình hay chỉ số dự đoán nào được huấn luyện ở đây.

## Bàn giao cho thành viên C

Đọc bảng trong `reports/tables/` theo hợp đồng `docs/data_contract.md` và `reports/tables/table_contract.json`. Gợi ý: cột số trận theo mùa từ season_summary, cơ cấu mặt sân từ surface_summary, thời lượng từ duration_by_surface_format, upset từ upsets_by_surface_format, tỷ lệ ace từ serve_by_surface, nhóm rank từ rank_group_performance. Chú thích luôn n, lọc completed và điều kiện rank/serve tương ứng. C có thể đọc trực tiếp các CSV mà không chạy lại thu thập.
"""
    (reports/'eda_findings.md').write_text(findings,encoding='utf-8')
    rows = []
    for col, spec in schema['properties'].items():
        rule=spec['x-csv']
        rows.append({'column':col,'dtype':rule['dtype'],'required_value':rule['core'],'meaning':spec['description']})
    source_files = pd.DataFrame([{'file':Path(f['path']).name,'rows':f['rows'],'sha256':f['sha256']} for f in (manifest or {}).get('files',[]) if f['rows'] is not None])
    inventory = f"""# Kiểm kê dữ liệu đầu vào

## Lựa chọn nguồn và phạm vi

Tác giả dữ liệu: **Jeff Sackmann / Tennis Abstract**. Nguồn gốc: {config['original_repository']}. Nguồn tải thực tế: https://github.com/{config['source_repository']}, commit `{config['source_commit']}`. Tại thời điểm triển khai ngày 28 tháng 10 năm 2026, URL kho gốc trả về 404; bản lưu trữ được dùng thay thế và không được coi là dịch vụ dữ liệu chính thức của ATP.

Chọn nguồn này vì có CSV theo mùa, ID người chơi ổn định, kết quả và thống kê giao bóng, từ điển dữ liệu và giấy phép công khai. Không chọn dữ liệu cược vì câu hỏi A B không cần odds; không trộn nguồn khác schema để tránh sai nối trận. Không cần API key hoặc scrape HTML. Bản lưu trữ tự mô tả là sao chép dữ liệu gốc; chưa kiểm chứng độc lập từng byte với kho gốc hiện không truy cập được.

Phạm vi mùa {config['start_season']}–{config['end_season']}, dữ liệu đơn nam trong file main draw cấp tour `atp_matches_YYYY.csv`. Giữ mã A M G F; loại các tên khớp `{config['excluded_tournament_patterns']}` không phân biệt hoa thường. Olympic có thể mang mã A/O tùy mùa nên lọc cả tên. Không bao gồm vòng loại, Challenger, Futures, đôi, WTA, Davis Cup, ATP Cup, United Cup, Laver Cup, Hopman Cup, Next Gen. Tour Finals chuẩn vẫn được giữ kể cả khi nguồn gán mã A. Không lấy mùa 2026 vì chưa kết thúc tại thời điểm triển khai. Phạm vi là các bản ghi hiện có, không cam kết đầy đủ toàn bộ lịch thi đấu.

## Phiên bản và số lượng

Đầu vào thật {len(raw):,} dòng, {len(schema['required'])-3} cột nguồn và 3 cột truy vết. Sau lọc và kiểm định giữ {len(m):,} dòng. Manifest chứa URL ghim commit, UTC tải, số byte, số dòng và SHA256 từng file. Raw bất biến; cache bị sửa sẽ làm pipeline dừng.

{md_table(source_files,0) if len(source_files) else 'Chế độ mẫu không tải nguồn mới; xem manifest gốc trong data/provenance/.'}

Nguồn mô tả rank và tuổi theo ngày giải; tourney_date thường là thứ Hai của tuần giải. match_num chỉ là định danh nội bộ, không bảo đảm thứ tự trận. Có giải mùa sau bắt đầu trong tháng 12 năm trước nên season và năm lịch được giữ riêng.

## Từ điển dữ liệu và schema

`data/schemas/tennis_schema.json` phiên bản 1.0.0 định nghĩa mọi cột đầu vào. CSV đọc dưới dạng string/null, mục x-csv quy định kiểu và ràng buộc ngữ nghĩa; module validation áp dụng các quy tắc này cùng kiểm tra liên trường. Mọi cột phải tồn tại, nhưng giá trị chỉ bắt buộc khi required_value=True. Giá trị thiếu là ô CSV trống; không ghi chuỗi số 0 thay thiếu.

{md_table(pd.DataFrame(rows))}

Đặc trưng xử lý được giải thích trong docs/data_contract.md. Mẫu thật cố định, có trùng chủ đích và trường thiếu, ở data/sample/tennis_sample.csv; nhãn và nguồn từng dòng ở data/sample/sample_manifest.json. Mẫu phát triển không được trộn vào dữ liệu phân tích thật. Các giá trị lỗi nhân tạo chỉ ở bộ kiểm thử.

## Giấy phép và ghi nguồn

Dữ liệu: Creative Commons Attribution NonCommercial ShareAlike 4.0, https://creativecommons.org/licenses/by-nc-sa/4.0/. Phải ghi tác giả, nguồn, nêu thay đổi; chỉ sử dụng phi thương mại và chia sẻ dữ liệu phái sinh theo cùng giấy phép. Bản LICENSE, README gốc và từ điển dữ liệu được giữ ở data/provenance/. Mã pipeline do dự án tạo riêng; không tuyên bố sở hữu bộ dữ liệu nguồn.

Cách ghi nguồn: Jeff Sackmann / Tennis Abstract. ATP Tennis Rankings Results and Stats. Bản lưu trữ Aneeshers/tennis-sackmann-archive, commit {config['source_commit']}, truy cập ngày 2026-10-28. CC BY-NC-SA 4.0. Dữ liệu được lọc phạm vi, đặt thiếu các giá trị không hợp lệ và thêm đặc trưng bằng pipeline trong dự án này.

## Hạn chế nguồn

Độ đầy đủ và độ chính xác phụ thuộc bản lưu trữ. Thiếu stats có thể có hệ thống; không có ngày thực tế từng trận, điều kiện thời tiết, odds, chấn thương hay shot-by-shot. Tên giải thay đổi cách viết và mã cấp giải có ngoại lệ; dùng ID cho nhóm giải và người chơi, đồng thời lọc tên theo phạm vi đã công bố. Các trường metadata và rank phản ánh thời điểm giải chứ không phải hiện tại.
"""
    (reports/'data_inventory.md').write_text(inventory,encoding='utf-8')


def write_table_contract(path: Path, tables: dict):
    contract = {'version':'1.0.0','format':'UTF-8 CSV, header, empty cell = null, decimal dot',
                'rates':'proportions 0–1, not percentages', 'tables':{}}
    for name, table in tables.items():
        fields=[]
        for c in table:
            unit = 'minutes' if 'minutes' in c else ('proportion' if c.endswith('_rate') or c in {'rate','share'} else 'count' if c.startswith('n_') or c in {'wins','losses','numerator','denominator','raw_missing','clean_missing','count'} else 'see table description')
            strings={'surface_group','metric','rank_group','player_name','field','score_status','match_id','source_file','tourney_name','winner_name','loser_name','score'}
            counts={'season','best_of','player_id','source_row','minutes','missing_duration','wins','losses','numerator','denominator','raw_n_rows','clean_n_rows','raw_missing','clean_missing','count'}
            dtype='string' if c in strings else 'integer' if c.startswith('n_') or c in counts else 'number'
            nullable=(dtype=='number' or c in {'score','minutes'})
            fields.append({'name':c,'dtype':dtype,'unit':unit,'nullable':nullable})
        contract['tables'][name]={'file':name+'.csv','population_and_definition':TABLE_NOTES[name],'columns':fields}
    path.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
