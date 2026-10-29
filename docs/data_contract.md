# Hợp đồng dữ liệu A B và C

Bổ sung: dataset tổng hợp GitHub + API dùng `data/schemas/tennis_common_schema.json` phiên bản 2.0.0, giữ cùng 52 cột và nâng ràng buộc ngữ nghĩa/định danh. Đọc [hợp đồng và cách dùng bộ chung](unified_schema.md); các mục phiên bản 1.0.0 dưới đây mô tả đầu vào nguồn và module B gốc.

Phiên bản 1.0.0. Dùng UTF-8 CSV với header; dấu chấm thập phân, ô trống là thiếu. Tỷ lệ trong CSV là số 0–1. Không dùng chuỗi `Unknown` trong cột số. Dùng ID người chơi để join, không dùng tên.

## Đầu vào của B

`data/schemas/tennis_schema.json` mô tả 49 cột nguồn và 3 cột provenance. JSON Schema định nghĩa bản ghi string/null vì CSV được đọc nguyên văn; `x-csv` quy định kiểu sau parse, bắt buộc giá trị, enum, ngưỡng. `validate_frame` áp dụng quy tắc x-csv và kiểm tra liên trường. JSON Schema thông thường một mình không thay thế kiểm định ngữ nghĩa này.

Một dòng là một trận trong file `atp_matches_YYYY.csv`. A thêm source_season (mùa trong tên file), source_file và source_row (dòng CSV gồm header là dòng 1). `load_raw` không đổi giá trị nguồn, trả DataFrame string nullable. `validate_frame(frame, schema)` trả bảng các vi phạm, không sửa dữ liệu; cột thiếu hoặc cột đầu vào không mong đợi làm dừng. Chỉ cho phép thêm đặc trưng khi gọi `allow_features=True` để kiểm định đầu ra.

Khóa trận sau parse là `tourney_id:match_num`. Không được dùng thứ tự match_num làm thứ tự thời gian. Cột tourney_date là ngày bắt đầu/tuần giải, không phải ngày từng trận. Mùa giải có thể bắt đầu tháng 12 năm trước; pipeline chỉ cho phép ngoại lệ này, còn sai mùa khác bị cách ly.

## Đầu ra của B

`clean_matches(raw, schema, config) -> CleanResult` chứa matches, excluded, quarantine, duplicates, issues, actions và flow. Hàm không sửa DataFrame đầu vào. Quy tắc cụ thể và thống kê tác động ở `reports/data_quality.md`. Mẫu và dữ liệu thật sử dụng cùng code, không có nhánh tính thống kê khác nhau.

`data/processed/tennis_matches.csv` có 52 cột đầu vào đã parse và các đặc trưng sau. `processed_contract.json` ghi đầy đủ danh sách cột, dtype khi chạy và tình trạng có giá trị thiếu; khi đọc CSV cần parse lại kiểu vì CSV không lưu dtype.

| Cột | Định nghĩa |
| --- | --- |
| match_id | Chuỗi tourney_id và dấu hai chấm và match_num nguyên; duy nhất sau xử lý |
| tournament_start_date | Ngày giải dạng ISO YYYY-MM-DD |
| season | Mùa nguồn, integer, dùng cho phân tích xu hướng |
| tournament_start_year | Năm lịch từ ngày giải; có thể khác season |
| surface_group | Hard Clay Grass Carpet hoặc Unknown; giữ surface gốc nullable |
| score_status | completed retired walkover defaulted abandoned unknown |
| is_completed | Tỷ số khớp cú pháp score và không có marker dừng; không kiểm chứng lại luật từng set |
| rank_pair_available | Hai rank có mặt và khác nhau |
| rank_gap | winner_rank trừ loser_rank; thiếu nếu thiếu một phía |
| is_upset | winner_rank lớn hơn loser_rank; nullable khi cặp rank không hợp lệ; khi tính tỷ lệ phải lọc is_completed |
| winner_rank_group và loser_rank_group | Top 10, 11–50, 51–100, 101+, Unknown |
| duration_review_flag | Minutes dương nhưng <20 hoặc >360; không đồng nghĩa dữ liệu sai |
| total_aces và total_double_faults | Tổng hai phía; thiếu nếu thiếu bất kỳ phía nào |
| w_ace_rate và l_ace_rate | ace / svpt |
| w_first_serve_in_rate và l_first_serve_in_rate | 1stIn / svpt |
| w_first_serve_win_rate và l_first_serve_win_rate | 1stWon / 1stIn |
| w_second_serve_win_rate và l_second_serve_win_rate | 2ndWon / (svpt − 1stIn) |
| w_break_point_save_rate và l_break_point_save_rate | bpSaved / bpFaced |

Mẫu số phải dương; không điền 0 cho tỷ lệ không xác định. Các tỷ lệ từng trận chỉ để khám phá; bảng serve_by_surface tính tỷ lệ gộp từ tổng số điểm trên các cặp tử/mẫu đủ dữ liệu.

`player_matches(matches)` trả hai dòng cho mỗi trận ở mọi trạng thái, phía thắng won=1 và thua won=0. Cần lọc is_completed khi muốn phân tích lượt thi đấu hoàn tất; đi walkover không có nghĩa người đó thực sự thi đấu. Tên cột player_id, player_name, player_rank, player_age, player_hand, rank_group; stats không có tiền tố w/l. Khóa ghép là match_id và player_id. Không cộng bảng này như số trận vì sẽ nhân đôi.

## Bảng dành cho C

`build_tables(matches, raw, schema)` trả dict tên → DataFrame. `verify_tables` đối soát tổng lượt, thắng, trận, upset và miền tỷ lệ. Danh sách cột và định nghĩa quần thể ở `reports/tables/table_contract.json`. Schema bảng giữ ổn định trong phiên bản 1.0.0; thêm cột hoặc đổi định nghĩa phải tăng phiên bản hợp đồng.

| Bảng | Gợi ý sử dụng |
| --- | --- |
| season_summary | Số trận theo mùa; duration coverage = n_duration / n_completed |
| surface_summary | Cơ cấu mặt sân; dùng n_matches cho toàn bộ bản ghi, n_completed cho trận hoàn tất |
| season_surface | Cơ cấu và chỉ số theo mùa và mặt sân |
| duration_by_surface_format | Thời lượng completed theo surface_group và best_of; luôn ghi n_duration |
| duration_sensitivity | Cùng định nghĩa nhưng bỏ cờ thời lượng để kiểm tra độ nhạy |
| duration_review | Danh sách truy vết từng trận có cờ thời lượng |
| upsets_by_surface_format | Upset theo mặt sân và thể thức; ghi n_ranked_completed |
| rank_group_performance | Tỷ lệ thắng theo rank của cả hai phía; ghi n_appearances |
| player_summary | Thắng thua theo player_id; số thắng tuyệt đối phụ thuộc số lần thi đấu |
| serve_by_surface | metric, rate, numerator, denominator, n_appearances, n_possible_appearances |
| missingness_by_season | Dạng dài theo season, field, n_rows, n_missing, missing_rate |
| numeric_summary | Count mean std min p25 median p75 p95 max theo biến số nguồn |
| score_status | Phân phối tình trạng trận của toàn bộ bản ghi giữ lại |
| quality_by_field | Tỷ lệ thiếu trước và sau; quần thể trước/sau khác nhau vì lọc phạm vi |

## Ví dụ C đọc dữ liệu

```python
from pathlib import Path
import pandas as pd

root = Path('.')
trend = pd.read_csv(root/'reports/tables/season_summary.csv')
serve = pd.read_csv(root/'reports/tables/serve_by_surface.csv')
ace = serve.loc[serve['metric'].eq('ace_rate')]
# Nếu hiển thị % thì nhân rate với 100; không nhân đôi trong CSV.
```

C không cần sửa code của A hoặc B. Không tự bỏ giá trị thiếu từ toàn bộ bảng trước khi chọn chỉ số; mỗi chỉ số có mẫu số riêng. Không gộp 3 set và 5 set rồi quy mọi chênh lệch cho mặt sân. Không diễn giải tương quan mô tả thành nhân quả.
