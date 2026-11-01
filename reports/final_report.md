# Báo cáo tổng hợp — Tennis Data Science

## Mục tiêu và phạm vi

Dự án mô tả dữ liệu đơn nam cấp tour historical 2015–2025: cơ cấu mặt sân, thời lượng, upset, nhóm rank và giao bóng. Đây không phải mô hình dự đoán và không kết luận nhân quả. Dataset historical có 27.574 bản ghi giữ lại; API/unified vận hành riêng, không gộp vào figure C.

## Đóng góp A, B và C

- **A:** provenance/checksum, schema, sample và kiểm định đầu vào.
- **B:** làm sạch, đặc trưng, kiểm tra chỉ số và 14 bảng CSV contract ổn định.
- **C:** validation bảng, sáu figure tái sử dụng, notebook trực quan hóa, insight có mẫu số và báo cáo này.

## Kết quả trực quan

| Figure | Kết quả truy vết |
| --- | --- |
| `season_matches` | 2020: 1.267; 2019: 2.610 (`season_summary.csv`) |
| `surface_composition` | Hard 15.948, Clay 8.450, Grass 3.176 (`surface_summary.csv`) |
| `duration_surface_format` | Median trong cùng `best_of`, dùng `n_duration` |
| `upset_surface_format` | Chỉ completed có `n_ranked_completed` |
| `rank_group_win_rate` | Top 10: 4.486/6.086 lượt, 73,7% |
| `ace_rate_surface` | Grass: 55.157/564.258, 9,78% |

## Tái lập và giới hạn

Kết quả môi trường thực tế được ghi vào `reports/final_acceptance.md`. Duration 2015 có coverage thấp; outlier 987 và 1.146 phút được giữ review. Mẫu số metric-specific không được thay bằng tổng trận. Credential `.env` không thuộc artifact, log hoặc report. `launchd` là bằng chứng macOS lịch sử, không phải trạng thái scheduler Windows.
