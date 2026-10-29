# Chất lượng dữ liệu trước và sau xử lý

Báo cáo được tạo tự động từ pipeline A và B. Các số dòng dưới đây là kết quả chạy thực tế, không phải số dự kiến.

## Đối soát số dòng

| metric | value |
| --- | --- |
| raw_rows | 30616 |
| excluded_scope_rows | 3042 |
| in_scope_rows | 27574 |
| quarantined_rows | 0 |
| exact_duplicates_removed | 0 |
| processed_rows | 27574 |
| optional_cells_set_missing | 122 |

Đẳng thức kiểm tra: raw = ngoài phạm vi + cách ly + bản sao bỏ + processed. Bản ghi bị loại vẫn được lưu trong `data/interim/`; không sửa file gốc.

## Kiểm định đầu vào

| severity | field | rule | n_issues |
| --- | --- | --- | --- |
| warning | l_2ndWon | second_wins_plus_df_gt_second_points | 3 |
| warning | loser_ht | below_minimum | 4 |
| warning | minutes | below_minimum | 59 |
| warning | w_2ndWon | second_wins_gt_second_points | 1 |
| warning | w_2ndWon | second_wins_plus_df_gt_second_points | 4 |
| warning | winner_ht | below_minimum | 5 |

Số vi phạm không bằng số ô sửa: một ô có thể vi phạm nhiều quy tắc; một thống kê giao bóng mâu thuẫn làm cả khối của người chơi đó được đặt thiếu.

Các vi phạm trong phạm vi phân tích:

| severity | field | rule | n_issues |
| --- | --- | --- | --- |
| warning | l_2ndWon | second_wins_plus_df_gt_second_points | 3 |
| warning | minutes | below_minimum | 59 |
| warning | w_2ndWon | second_wins_gt_second_points | 1 |
| warning | w_2ndWon | second_wins_plus_df_gt_second_points | 4 |

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

Có 0 vi phạm schema/ngữ nghĩa còn lại; ID trận duy nhất: True. Có 39 trận được gắn cờ thời lượng. Các giá trị cực đoan còn lại cần được đối chiếu nguồn trước khi diễn giải riêng.

Tổng ô thiếu trong 52 cột đầu vào: 119,932/1,592,032 trước lọc; 84,288/1,433,848 sau xử lý. Hai quần thể khác nhau, không dùng chênh lệch này để tuyên bố pipeline đã cải thiện tỷ lệ thiếu. Pipeline có thể tăng tỷ lệ thiếu vì loại giá trị sai.

Chi tiết theo cột: `reports/tables/quality_by_field.csv`; theo mùa: `reports/tables/missingness_by_season.csv`. Bằng chứng từng dòng: `data/interim/validation_issues.csv`, `cleaning_actions.csv`, `quarantine.csv`, `duplicates.csv`, `excluded_scope.csv`.

## Hạn chế còn lại

Kiểm định tự động không chứng minh toàn bộ bản ghi đúng hoặc nguồn thu thập đầy đủ. RET, DEF, W/O giữ lại cho kiểm kê nhưng loại khỏi so sánh thi đấu hoàn tất. Nhãn completed chỉ dựa vào cú pháp tỷ số và marker, không xác minh số set bằng luật tennis. Thiếu thống kê có thể có hệ thống theo giải/mùa, nên kết quả trên phần có dữ liệu có thể lệch. Chưa đối chiếu từng trận với bảng điểm chính thức.
