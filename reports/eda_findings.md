# Phân tích khám phá tennis giai đoạn 2015 đến 2025

## Phạm vi và câu hỏi nghiên cứu

Phân tích 27,574 bản ghi đơn nam cấp tour theo phạm vi A M G F đã lọc giải đồng đội, Olympic và Next Gen. Nguồn do Jeff Sackmann / Tennis Abstract biên soạn, tải từ bản lưu trữ được ghim commit. Mục tiêu là mô tả cơ cấu mặt sân, khác biệt thời lượng và giao bóng, quan hệ thứ hạng với kết quả, xu hướng số trận theo mùa. Không xây dựng mô hình dự đoán trong phần A và B.

Đơn vị gốc là một trận. Khi phân tích người chơi, mỗi trận tạo hai lượt người chơi. `season` lấy từ tên file; `tournament_start_year` là năm lịch của ngày giải. Không gọi tourney_date là ngày diễn ra trận và không dùng match_num để suy ra trình tự thời gian.

## Kết quả chính

Có 26,599 trận hoàn tất trên 27,574 bản ghi (96.46%). Có 26,524 trận đủ hai rank khác nhau; 9,408 trận người có thứ hạng thấp hơn thắng, tỷ lệ 35.47%. 75 trận hoàn tất bị loại khỏi mẫu số upset vì thiếu rank hoặc hai rank bằng nhau. Upset ở đây không xét tỷ lệ cược và không có nghĩa là kết quả khó dự đoán theo mọi thước đo.

Nhóm Top 10 thắng 4,486/6,086 lượt thi đấu hoàn tất (73.7%). Đây là thống kê theo thứ hạng trước giải của từng lượt, không phải chỉ thống kê rank của người thắng.

Tỷ lệ ace gộp cao nhất trên Grass: 55,157/564,258 = 9.78%; thấp nhất trên Clay: 5.42%. Chênh lệch 4.35 điểm phần trăm. Đây là tương quan mô tả, còn khác biệt người chơi, giải và thể thức.

Mùa 2020 có 1,267 trận so với 2,610 của 2019, giảm 51.5%. Dữ liệu chứng minh sự giảm số trận trong nguồn; nguyên nhân và tác động của từng thay đổi lịch giải cần nguồn bổ sung, không thể suy ra chỉ từ bảng này.

Mùa có độ phủ thời lượng thấp nhất là 2015: 1,315/2,527 trận hoàn tất (52.0%). Vì vậy xu hướng median thời lượng theo mùa chỉ phản ánh phần có dữ liệu và không thể coi là thay đổi toàn tour.

## Cơ cấu dữ liệu và xu hướng mùa giải

| season | n_matches | n_completed | n_tournaments | n_duration | median_minutes | n_ranked_completed | n_upsets | upset_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2015 | 2630 | 2527 | 66 | 1315 | 98.000 | 2518 | 782 | 0.311 |
| 2016 | 2626 | 2527 | 66 | 2520 | 100.000 | 2520 | 814 | 0.323 |
| 2017 | 2633 | 2530 | 67 | 2501 | 102.000 | 2526 | 874 | 0.346 |
| 2018 | 2637 | 2555 | 67 | 2544 | 104.000 | 2552 | 930 | 0.364 |
| 2019 | 2610 | 2531 | 66 | 2527 | 105.000 | 2515 | 975 | 0.388 |
| 2020 | 1267 | 1237 | 32 | 1237 | 115.000 | 1229 | 449 | 0.365 |
| 2021 | 2489 | 2408 | 61 | 2406 | 108.000 | 2402 | 895 | 0.373 |
| 2022 | 2632 | 2547 | 68 | 2428 | 110.000 | 2545 | 908 | 0.357 |
| 2023 | 2703 | 2614 | 65 | 2614 | 115.000 | 2601 | 952 | 0.366 |
| 2024 | 2703 | 2607 | 65 | 2484 | 110.000 | 2604 | 942 | 0.362 |
| 2025 | 2644 | 2516 | 60 | 2398 | 109.000 | 2512 | 887 | 0.353 |

| surface_group | n_matches | n_completed | n_tournaments | n_duration | median_minutes | n_ranked_completed | n_upsets | upset_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Clay | 8450 | 8183 | 221 | 7672 | 107.000 | 8169 | 2960 | 0.362 |
| Grass | 3176 | 3078 | 76 | 2768 | 113.000 | 3067 | 1081 | 0.352 |
| Hard | 15948 | 15338 | 386 | 14534 | 105.000 | 15288 | 5367 | 0.351 |

Mỗi tỷ lệ upset có mẫu số riêng `n_ranked_completed`; median_minutes chỉ dùng `n_duration` trận hoàn tất có thời lượng. Các tỷ lệ được lưu dạng 0–1 trong CSV, khi viết báo cáo mới đổi sang phần trăm. Số giải dùng tourney_id và chỉ tính các giải có bản ghi được giữ lại, không phải kiểm kê lịch ATP chính thức.

## So sánh thời lượng theo mặt sân và thể thức

| surface_group | best_of | n_matches | n_duration | missing_duration | mean_minutes | std_minutes | p25_minutes | median_minutes | p75_minutes | p95_minutes | max_minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Clay | 3 | 6829 | 6676 | 153 | 107.749 | 34.751 | 81.000 | 102.000 | 131.000 | 168.000 | 987.000 |
| Clay | 5 | 1354 | 996 | 358 | 156.333 | 47.740 | 121.000 | 146.000 | 186.000 | 248.250 | 365.000 |
| Grass | 3 | 1849 | 1662 | 187 | 99.981 | 29.479 | 77.000 | 95.000 | 121.000 | 154.000 | 203.000 |
| Grass | 5 | 1229 | 1106 | 123 | 152.931 | 46.000 | 117.000 | 146.000 | 184.000 | 236.000 | 396.000 |
| Hard | 3 | 12682 | 11990 | 692 | 103.518 | 33.073 | 79.000 | 97.000 | 125.000 | 162.000 | 1,146.000 |
| Hard | 5 | 2656 | 2544 | 112 | 161.922 | 47.390 | 124.000 | 155.000 | 195.000 | 246.850 | 345.000 |

So sánh chính phải nằm trong cùng best_of; gộp 3 set và 5 set sẽ trộn ảnh hưởng thể thức với mặt sân. Bảng `duration_sensitivity.csv` cho kết quả khi bỏ cờ thời lượng cực đoan. `season_surface.csv` hỗ trợ xem tiếp thay đổi theo mùa. Các thống kê không điều chỉnh trình độ người chơi, vòng đấu, giải hay thời tiết nên không kết luận mặt sân gây ra chênh lệch.

Đối chiếu kết quả chính và độ nhạy:

| surface_group | best_of | n_duration_main | n_duration_sensitivity | mean_minutes_main | mean_minutes_sensitivity | median_minutes_main | median_minutes_sensitivity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Clay | 3 | 6676 | 6675 | 107.749 | 107.617 | 102.000 | 102.000 |
| Clay | 5 | 996 | 995 | 156.333 | 156.124 | 146.000 | 146.000 |
| Grass | 3 | 1662 | 1662 | 99.981 | 99.981 | 95.000 | 95.000 |
| Grass | 5 | 1106 | 1105 | 152.931 | 152.711 | 146.000 | 146.000 |
| Hard | 3 | 11990 | 11989 | 103.518 | 103.431 | 97.000 | 97.000 |
| Hard | 5 | 2544 | 2544 | 161.922 | 161.922 | 155.000 | 155.000 |

Các thời lượng trên 600 phút của trận 3 set cần kiểm chứng nguồn trước khi dùng riêng hoặc dùng mean làm kết luận:

| match_id | tourney_name | winner_name | loser_name | score | minutes |
| --- | --- | --- | --- | --- | --- |
| 2016-M001:294 | Sydney | Gilles Muller | Jeremy Chardy | 7-6(5) 6-3 | 1146 |
| 2017-0308:297 | Munich | Hyeon Chung | Martin Klizan | 6-4 3-6 6-2 | 987 |

Không suy đoán giá trị sửa từ các con số này. Danh sách đầy đủ cờ kiểm tra nằm ở `duration_review.csv`; cờ <20 phút thường là bỏ cuộc sớm, vì vậy không tự xem mọi cờ là lỗi dữ liệu. Median và so sánh độ nhạy được ưu tiên cho diễn giải thời lượng.

## Phân phối thứ hạng và hiệu suất theo nhóm

| rank_group | n_appearances | wins | n_players | losses | win_rate |
| --- | --- | --- | --- | --- | --- |
| 101+ | 10820 | 4040 | 763 | 6780 | 0.373 |
| 11–50 | 19378 | 10558 | 206 | 8820 | 0.545 |
| 51–100 | 16839 | 7502 | 322 | 9337 | 0.446 |
| Top 10 | 6086 | 4486 | 46 | 1600 | 0.737 |
| Unknown | 75 | 13 | 50 | 62 | 0.173 |

Nhóm Top 10, 11–50, 51–100, 101+ thay đổi theo rank trước mỗi giải; Unknown không bị ép vào 101+. Cùng một người có thể xuất hiện ở nhiều nhóm qua thời gian. Tổng lượt bằng hai lần số trận hoàn tất, tổng thắng bằng số trận hoàn tất. Danh sách người chơi trong `player_summary.csv` nối bằng ID, không bằng tên. Số thắng tuyệt đối chịu ảnh hưởng số lần tham dự.

## Giao bóng và mẫu số

| surface_group | metric | n_appearances | n_possible_appearances | numerator | denominator | rate |
| --- | --- | --- | --- | --- | --- | --- |
| Clay | ace_rate | 16355 | 16366 | 71323 | 1314745 | 0.054 |
| Clay | first_serve_win_rate | 16355 | 16366 | 563860 | 818600 | 0.689 |
| Clay | second_serve_win_rate | 16353 | 16366 | 250492 | 496145 | 0.505 |
| Grass | ace_rate | 6154 | 6156 | 55157 | 564258 | 0.098 |
| Grass | first_serve_win_rate | 6154 | 6156 | 262953 | 354072 | 0.743 |
| Grass | second_serve_win_rate | 6154 | 6156 | 109594 | 210186 | 0.521 |
| Hard | ace_rate | 30658 | 30676 | 219096 | 2477213 | 0.088 |
| Hard | first_serve_win_rate | 30658 | 30676 | 1103816 | 1518295 | 0.727 |
| Hard | second_serve_win_rate | 30658 | 30676 | 486842 | 958918 | 0.508 |

Tỷ lệ ace = tổng ace / tổng điểm giao bóng trên các lượt có đủ cặp số liệu. Tỷ lệ thắng giao bóng hai dùng `svpt - 1stIn`, bao gồm điểm lỗi kép. Không lấy trung bình đơn giản tỷ lệ từng trận. Từng metric có n_appearances và denominator riêng; thiếu một chỉ số không làm mất toàn bộ trận khỏi các phân tích không liên quan.

## Phân phối và giới hạn diễn giải

`numeric_summary.csv` chứa count, mean, std, min, p25, median, p75, p95, max cho các biến số gốc. `score_status.csv` cho phân phối tình trạng trận; `missingness_by_season.csv` cho sự thiếu dữ liệu theo mùa. Notebook B vẽ phân phối thời lượng và thể hiện các so sánh chính trực tiếp từ bảng đầu ra.

Đây là thống kê mô tả của dữ liệu quan sát đã chọn, không phải mẫu ngẫu nhiên của mọi trận tennis. Các trận lặp lại cùng người chơi và cùng giải có phụ thuộc; không diễn giải p-value độc lập hay khoảng tin cậy nhị thức đơn giản. Không dùng chênh lệch làm bằng chứng nhân quả. So sánh theo năm bị ảnh hưởng lịch giải, số vòng, phạm vi nguồn và độ đầy đủ thống kê. Không suy rộng sang WTA, Challenger, vòng loại hoặc giải đồng đội.

Nguồn thiếu một số thống kê; không điền giá trị có thể bịa ra hiệu suất. Cấu trúc winner/loser đã chứa kết quả: nếu C hoặc nhóm mở rộng sang dự đoán thì không dùng các cột hậu trận, phải tái thiết kế hướng người chơi và chia tập theo thời gian. Chưa có mô hình hay chỉ số dự đoán nào được huấn luyện ở đây.

## Bàn giao cho thành viên C

Đọc bảng trong `reports/tables/` theo hợp đồng `docs/data_contract.md` và `reports/tables/table_contract.json`. Gợi ý: cột số trận theo mùa từ season_summary, cơ cấu mặt sân từ surface_summary, thời lượng từ duration_by_surface_format, upset từ upsets_by_surface_format, tỷ lệ ace từ serve_by_surface, nhóm rank từ rank_group_performance. Chú thích luôn n, lọc completed và điều kiện rank/serve tương ứng. C có thể đọc trực tiếp các CSV mà không chạy lại thu thập.
