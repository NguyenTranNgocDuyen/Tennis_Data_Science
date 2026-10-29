# Nghiệm thu công việc A và B

Kiểm tra trên macOS ARM64, Python 3.13.7, ngày 28 tháng 10 năm 2026. Đây là kết quả thực thi trên bộ dữ liệu bàn giao.

| Kiểm tra | Kết quả |
| --- | --- |
| Đầu ra bắt buộc của A và B theo tài liệu | Đủ cả 12 đường dẫn bắt buộc |
| Tải dữ liệu thật | 11 CSV nguồn, 30.616 dòng, commit ghim và SHA256 từng file |
| Dữ liệu sau lọc và xử lý | 27.574 trận, 55.148 lượt người chơi ở mọi trạng thái |
| Pipeline trên dữ liệu thật | Thành công; 0 vi phạm schema/ngữ nghĩa còn lại theo quy tắc đã triển khai |
| Pipeline trên mẫu | 127 dòng đầu vào, 125 dòng giữ lại, bỏ đúng 2 bản sao chủ đích |
| Kiểm thử tự động | 49 passed trong 2,86 giây, lệnh .venv/bin/python -m pytest -q |
| Hợp đồng bảng mẫu và thật | Cùng phiên bản 1.0.0, cùng 14 bảng, cột, kiểu và định nghĩa |
| Đối soát thống kê | Tổng trận, hai lượt mỗi trận, tổng thắng, mẫu số upset, miền tỷ lệ đều đạt |
| Notebook B | 10/10 ô code thực thi, 0 lỗi, 5 hình |
| Kiểm tra hình | Đã xem cả 5 hình; nhãn, trục, phần trăm và bố cục đọc được |
| Tái lập offline | 26 file đầu ra khớp SHA256 hoàn toàn ở thư mục tạm mới, 0 khác biệt |
| Cache nguồn | 11 file CSV được xác minh; test cache bị sửa phải dừng |

## Cách kiểm tra lại

```bash
.venv/bin/python scripts/run_pipeline.py --offline
.venv/bin/python scripts/run_pipeline.py --sample
.venv/bin/python -m pytest -q
.venv/bin/python scripts/verify_reproducibility.py
.venv/bin/python scripts/execute_notebook.py
```

Chi tiết máy đọc được: run_manifest.json, reproducibility.json và notebook_execution.json. Manifest đầu ra kiểm tra các file của pipeline; báo cáo nghiệm thu này và notebook được kiểm tra riêng. Cấu trúc yêu cầu và ánh xạ đầu ra: docs/assignment_checklist.md.

## Giới hạn nghiệm thu

Kết quả 0 vi phạm chỉ áp dụng cho các quy tắc đã cài đặt, không chứng minh toàn bộ dữ liệu nguồn chính xác. Có 39 cờ thời lượng, trong đó 4 trận completed; hai thời lượng 987 và 1.146 phút ở thể thức 3 set cần đối chiếu độc lập. Các giá trị này được giữ có cờ, có bảng độ nhạy và không bị sửa suy đoán. Mùa 2015 chỉ có 1.315/2.527 thời lượng trận completed (52,0%). Vì vậy không diễn giải xu hướng thời lượng như thay đổi toàn tour.

Các thống kê mô tả không điều chỉnh toàn bộ yếu tố nhiễu và không chứng minh quan hệ nhân quả. Phân tích và dữ liệu phù hợp mục đích đồ án trong phạm vi đã công bố; vẫn cần nhóm hiểu phương pháp, ghi nguồn và tuân thủ giấy phép dữ liệu khi nộp hoặc chia sẻ.
