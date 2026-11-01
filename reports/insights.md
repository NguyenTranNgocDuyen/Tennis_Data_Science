# Insight trực quan hóa — dữ liệu historical 2015–2025

Các figure ở `reports/figures/` truy vết về CSV trong `reports/tables/`; tỷ lệ chỉ đổi sang phần trăm ở lớp hiển thị.

## Khối lượng trận

`season_matches` cho thấy 2020 có 1.267 bản ghi được giữ lại, so với 2.610 ở 2019 (giảm 51,5%). Đây là mô tả số bản ghi trong nguồn, không xác định nguyên nhân hay tác động lịch thi đấu. Nguồn: `season_summary.csv`.

## Mặt sân và thời lượng

Hard có 15.948/27.574 bản ghi; Clay 8.450 và Grass 3.176. Median duration phải so sánh trong cùng `best_of`: Hard 3-set là 97 phút, Hard 5-set là 155 phút. Median chỉ dùng `n_duration`; năm 2015 chỉ có 1.315/2.527 trận completed có duration. Giá trị 987 và 1.146 phút được giữ như cờ review, vì vậy không dùng mean làm kết luận chính. Nguồn: `surface_summary.csv`, `duration_by_surface_format.csv`, `season_summary.csv`.

## Upset, rank và giao bóng

Upset rate chỉ áp dụng completed matches có hai rank khác nhau (`n_ranked_completed`); nó không phải xác suất dự đoán hay tỷ lệ cược. Top 10 thắng 4.486/6.086 lượt người chơi completed (73,7%); mỗi trận góp hai lượt. Grass có ace rate gộp 55.157/564.258 = 9,78%, Clay là 5,42%. Khác biệt chưa điều chỉnh người chơi, giải, mùa hoặc thể thức nên chỉ là liên hệ mô tả. Nguồn: `upsets_by_surface_format.csv`, `rank_group_performance.csv`, `serve_by_surface.csv`.
