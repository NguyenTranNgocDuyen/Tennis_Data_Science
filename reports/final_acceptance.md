# Nghiệm thu cuối — phần C và môi trường Windows

Ngày chạy: 01/11/2026, múi giờ Asia/Ho_Chi_Minh. Môi trường: Windows 10.0.26200.0, Python 3.13.17, virtual environment `.venv`. Commit tại thời điểm kiểm tra: `da5412f` (các thay đổi phần C chưa commit).

| Kiểm tra                           | Kết quả thực tế                                                                                                                             |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Cài dependency                     | Pass: cài từ `requirements.txt` vào `.venv`                                                                                                 |
| Full test suite                    | Pass: **158 passed** trong 14,86 giây; dùng `--basetemp .pytest-tmp -p no:cacheprovider` vì `%TEMP%` bị từ chối quyền trong sandbox Windows |
| Test visualization                 | Đã nằm trong full suite; kiểm tra contract, proportion 0–1, immutability, headless, annotation và PNG/SVG export                            |
| Export C                           | Pass: 6 PNG và 6 SVG ở `reports/figures/` từ historical hand-off tables                                                                     |
| Notebook C                         | Pass: 3 code cells thực thi bằng kernel `tennis-khdl`; notebook không đọc `.env` hoặc gọi API                                               |
| Pipeline sample                    | Pass: 127 input, bỏ 2 duplicate, giữ 125, 0 post-clean issue, 14 tables ở `runs/sample`                                                     |
| Reproducibility historical offline | Pass: 26 artifacts khớp SHA-256, 11 raw files verified, mismatches: 0                                                                       |

## Lệnh đã chạy

```powershell
.\.venv\Scripts\python -m pytest -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python scripts\export_visualizations.py
.\.venv\Scripts\python scripts\run_pipeline.py --sample
```

Notebook C được thực thi qua `nbclient` bằng kernel cục bộ `tennis-khdl` và output được lưu trong notebook. `scripts/verify_reproducibility.py` cũng đã được chạy nhưng không thể hoàn tất do artifact historical bị thiếu; không tải lại hoặc tạo dữ liệu thay thế.

Các số 49/80/112/143 trong báo cáo cũ là mốc lịch sử của các cấu hình/dataset khác. Kết quả chuẩn cho working tree hiện tại, trong phạm vi artifact đang có, là **158 passed**. Scheduler `launchd` và trạng thái GitHub/PR không được xác minh trên Windows trong đợt này.
