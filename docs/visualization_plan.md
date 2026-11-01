# Kế hoạch trực quan hóa — Thành viên C

Phần C dùng **chỉ** các bảng historical tại `reports/tables/`; không gộp snapshot API/unified. Nguồn sự thật cho cột, đơn vị, quần thể và tỷ lệ là `reports/tables/table_contract.json`. CSV lưu tỷ lệ 0–1, chỉ layer hiển thị đổi sang phần trăm.

| Figure | Bảng nguồn | Chỉ số/mẫu số | Giới hạn bắt buộc |
| --- | --- | --- | --- |
| `season_matches` | `season_summary.csv` | `n_matches`, mọi record giữ lại | 2020 không chứng minh nguyên nhân |
| `surface_composition` | `surface_summary.csv` | `n_matches`, mọi record giữ lại | Không thay bằng `n_completed` |
| `duration_surface_format` | `duration_by_surface_format.csv` | `median_minutes`, `n_duration` | Tách `best_of`; 2015 coverage thấp; 987/1146 chỉ review |
| `upset_surface_format` | `upsets_by_surface_format.csv` | `upset_rate`, `n_ranked_completed` | Upset = `winner_rank > loser_rank` |
| `rank_group_win_rate` | `rank_group_performance.csv` | `win_rate`, `n_appearances` | Một trận completed góp hai lượt người chơi |
| `ace_rate_surface` | `serve_by_surface.csv`, `ace_rate` | `rate`, tử/mẫu, `n_appearances` | Tỷ lệ gộp, không phải mean per-match |

Mỗi chart có title, đơn vị, source, mẫu số và limitation. Module `src/visualization/` sở hữu validation, formatting, annotation và export; notebook C chỉ điều phối.
