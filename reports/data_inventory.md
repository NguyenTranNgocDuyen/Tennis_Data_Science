# Kiểm kê dữ liệu đầu vào

## Lựa chọn nguồn và phạm vi

Tác giả dữ liệu: **Jeff Sackmann / Tennis Abstract**. Nguồn gốc: https://github.com/JeffSackmann/tennis_atp. Nguồn tải thực tế: https://github.com/Aneeshers/tennis-sackmann-archive, commit `83733587353df8a41f2fd4f516147d5aa83f5a8d`. Tại thời điểm triển khai ngày 28 tháng 10 năm 2026, URL kho gốc trả về 404; bản lưu trữ được dùng thay thế và không được coi là dịch vụ dữ liệu chính thức của ATP.

Chọn nguồn này vì có CSV theo mùa, ID người chơi ổn định, kết quả và thống kê giao bóng, từ điển dữ liệu và giấy phép công khai. Không chọn dữ liệu cược vì câu hỏi A B không cần odds; không trộn nguồn khác schema để tránh sai nối trận. Không cần API key hoặc scrape HTML. Bản lưu trữ tự mô tả là sao chép dữ liệu gốc; chưa kiểm chứng độc lập từng byte với kho gốc hiện không truy cập được.

Phạm vi mùa 2015–2025, dữ liệu đơn nam trong file main draw cấp tour `atp_matches_YYYY.csv`. Giữ mã A M G F; loại các tên khớp `['(?i)\\b(?:atp|united|laver|hopman) cup\\b', '(?i)olympics', '(?i)next\\s*gen']` không phân biệt hoa thường. Olympic có thể mang mã A/O tùy mùa nên lọc cả tên. Không bao gồm vòng loại, Challenger, Futures, đôi, WTA, Davis Cup, ATP Cup, United Cup, Laver Cup, Hopman Cup, Next Gen. Tour Finals chuẩn vẫn được giữ kể cả khi nguồn gán mã A. Không lấy mùa 2026 vì chưa kết thúc tại thời điểm triển khai. Phạm vi là các bản ghi hiện có, không cam kết đầy đủ toàn bộ lịch thi đấu.

## Phiên bản và số lượng

Đầu vào thật 30,616 dòng, 49 cột nguồn và 3 cột truy vết. Sau lọc và kiểm định giữ 27,574 dòng. Manifest chứa URL ghim commit, UTC tải, số byte, số dòng và SHA256 từng file. Raw bất biến; cache bị sửa sẽ làm pipeline dừng.

| file | rows | sha256 |
| --- | --- | --- |
| atp_matches_2015.csv | 2943 | 20c1f723df86b367f3ec205bbda3d8a7163fa6d4e46dcfda15095e24965bc5ed |
| atp_matches_2016.csv | 2941 | 86dda3871cb79d3226a047774c8fc97b86267cfe96709dea832a347dfbf81684 |
| atp_matches_2017.csv | 2911 | 4bb295788c37487b120cd39171d413cef0ebc6f4c2d9fa40b7261f5143f3719f |
| atp_matches_2018.csv | 2897 | 0363dc6012190f337fcf34b4ca443634f192c4670cc6c14c94342a54b9adf7eb |
| atp_matches_2019.csv | 2806 | 7f1a21451ff622bb0c6a09690898db46d51e59dcdf08086d369753822e1d5478 |
| atp_matches_2020.csv | 1462 | 985a917b72d5efb7dd5ef9df8ecc58c637ed6b88561ccad364653af71ac12da0 |
| atp_matches_2021.csv | 2733 | b9b1d31a4b0b9273b8f338cbb1347c5a847ad2361334ec760a286f5990fba347 |
| atp_matches_2022.csv | 2917 | 7190042565ab8400e74f44fda60700acb36ddf3c82d393f331a07589e05b5f52 |
| atp_matches_2023.csv | 2986 | 9b9671aa7c8156e74c2e4466675b7ed4e762bb8a58b7237a30daefd84ffceff5 |
| atp_matches_2024.csv | 3076 | 73aec32247a0db68d8aa8fd8003eefea132905177f1cb145502d9215b53311be |
| atp_matches_2025.csv | 2944 | 78c356ef9328b89ae58a17564d61c02cdad2a3a007f6b8af5cfc17992b11bb2d |

Nguồn mô tả rank và tuổi theo ngày giải; tourney_date thường là thứ Hai của tuần giải. match_num chỉ là định danh nội bộ, không bảo đảm thứ tự trận. Có giải mùa sau bắt đầu trong tháng 12 năm trước nên season và năm lịch được giữ riêng.

## Từ điển dữ liệu và schema

`data/schemas/tennis_schema.json` phiên bản 1.0.0 định nghĩa mọi cột đầu vào. CSV đọc dưới dạng string/null, mục x-csv quy định kiểu và ràng buộc ngữ nghĩa; module validation áp dụng các quy tắc này cùng kiểm tra liên trường. Mọi cột phải tồn tại, nhưng giá trị chỉ bắt buộc khi required_value=True. Giá trị thiếu là ô CSV trống; không ghi chuỗi số 0 thay thiếu.

| column | dtype | required_value | meaning |
| --- | --- | --- | --- |
| tourney_id | string | True | Mã giải có tiền tố mùa giải; không suy luận cấu trúc phần còn lại. |
| tourney_name | string | True | Tên giải theo nguồn. |
| surface | string | False | Mặt sân; trống là chưa biết. |
| draw_size | integer | False | Quy mô nhánh đấu, có thể làm tròn lên lũy thừa 2. |
| tourney_level | string | True | G Grand Slam; M Masters; A tour khác; F cuối mùa; D Davis Cup; mã khác giữ trong raw. |
| tourney_date | date8 | True | YYYYMMDD ngày bắt đầu/tuần giải; KHÔNG phải ngày thực tế từng trận. |
| match_num | integer | True | Mã trận trong giải; KHÔNG đảm bảo thứ tự thời gian. |
| winner_id | integer | True | Mã người chơi ổn định, dùng để join của người thắng. |
| winner_seed | string | False | Hạt giống (chuỗi, có thể không chỉ là số) của người thắng. |
| winner_entry | string | False | Diện vào giải Q WC LL PR... của người thắng. |
| winner_name | string | True | Tên của người thắng. |
| winner_hand | string | False | Tay giao bóng R L U của người thắng. |
| winner_ht | integer | False | Chiều cao cm của người thắng. |
| winner_ioc | string | False | Mã quốc gia IOC của người thắng. |
| winner_age | number | False | Tuổi ở ngày giải của người thắng. |
| loser_id | integer | True | Mã người chơi ổn định, dùng để join của người thua. |
| loser_seed | string | False | Hạt giống (chuỗi, có thể không chỉ là số) của người thua. |
| loser_entry | string | False | Diện vào giải Q WC LL PR... của người thua. |
| loser_name | string | True | Tên của người thua. |
| loser_hand | string | False | Tay giao bóng R L U của người thua. |
| loser_ht | integer | False | Chiều cao cm của người thua. |
| loser_ioc | string | False | Mã quốc gia IOC của người thua. |
| loser_age | number | False | Tuổi ở ngày giải của người thua. |
| score | string | False | Tỷ số nguyên văn; RET bỏ cuộc; W/O không thi đấu; DEF truất quyền. |
| best_of | integer | True | Thể thức tối đa 3 hoặc 5 set. |
| round | string | True | Vòng đấu theo mã nguồn. |
| minutes | integer | False | Thời lượng phút; thiếu không được thay bằng 0. |
| w_ace | integer | False | Số ace của người thắng. |
| w_df | integer | False | Số lỗi kép của người thắng. |
| w_svpt | integer | False | Số điểm giao bóng của người thắng. |
| w_1stIn | integer | False | Số giao bóng một vào sân của người thắng. |
| w_1stWon | integer | False | Số điểm thắng khi giao bóng một của người thắng. |
| w_2ndWon | integer | False | Số điểm thắng khi giao bóng hai của người thắng. |
| w_SvGms | integer | False | Số game giao bóng của người thắng. |
| w_bpSaved | integer | False | Số break point cứu được của người thắng. |
| w_bpFaced | integer | False | Số break point đối mặt của người thắng. |
| l_ace | integer | False | Số ace của người thua. |
| l_df | integer | False | Số lỗi kép của người thua. |
| l_svpt | integer | False | Số điểm giao bóng của người thua. |
| l_1stIn | integer | False | Số giao bóng một vào sân của người thua. |
| l_1stWon | integer | False | Số điểm thắng khi giao bóng một của người thua. |
| l_2ndWon | integer | False | Số điểm thắng khi giao bóng hai của người thua. |
| l_SvGms | integer | False | Số game giao bóng của người thua. |
| l_bpSaved | integer | False | Số break point cứu được của người thua. |
| l_bpFaced | integer | False | Số break point đối mặt của người thua. |
| winner_rank | integer | False | Thứ hạng ATP trước hoặc tại ngày giải; số nhỏ là hạng cao của người thắng. |
| winner_rank_points | integer | False | Điểm xếp hạng của người thắng. |
| loser_rank | integer | False | Thứ hạng ATP trước hoặc tại ngày giải; số nhỏ là hạng cao của người thua. |
| loser_rank_points | integer | False | Điểm xếp hạng của người thua. |
| source_season | integer | True | Mùa theo tên file, có thể khác năm của tourney_date. |
| source_file | string | True | Tên CSV gốc dùng truy vết. |
| source_row | integer | True | Số dòng CSV gốc tính cả header là dòng 1. |

Đặc trưng xử lý được giải thích trong docs/data_contract.md. Mẫu thật cố định, có trùng chủ đích và trường thiếu, ở data/sample/tennis_sample.csv; nhãn và nguồn từng dòng ở data/sample/sample_manifest.json. Mẫu phát triển không được trộn vào dữ liệu phân tích thật. Các giá trị lỗi nhân tạo chỉ ở bộ kiểm thử.

## Giấy phép và ghi nguồn

Dữ liệu: Creative Commons Attribution NonCommercial ShareAlike 4.0, https://creativecommons.org/licenses/by-nc-sa/4.0/. Phải ghi tác giả, nguồn, nêu thay đổi; chỉ sử dụng phi thương mại và chia sẻ dữ liệu phái sinh theo cùng giấy phép. Bản LICENSE, README gốc và từ điển dữ liệu được giữ ở data/provenance/. Mã pipeline do dự án tạo riêng; không tuyên bố sở hữu bộ dữ liệu nguồn.

Cách ghi nguồn: Jeff Sackmann / Tennis Abstract. ATP Tennis Rankings Results and Stats. Bản lưu trữ Aneeshers/tennis-sackmann-archive, commit 83733587353df8a41f2fd4f516147d5aa83f5a8d, truy cập ngày 2026-10-28. CC BY-NC-SA 4.0. Dữ liệu được lọc phạm vi, đặt thiếu các giá trị không hợp lệ và thêm đặc trưng bằng pipeline trong dự án này.

## Hạn chế nguồn

Độ đầy đủ và độ chính xác phụ thuộc bản lưu trữ. Thiếu stats có thể có hệ thống; không có ngày thực tế từng trận, điều kiện thời tiết, odds, chấn thương hay shot-by-shot. Tên giải thay đổi cách viết và mã cấp giải có ngoại lệ; dùng ID cho nhóm giải và người chơi, đồng thời lọc tên theo phạm vi đã công bố. Các trường metadata và rank phản ánh thời điểm giải chứ không phải hiện tại.
