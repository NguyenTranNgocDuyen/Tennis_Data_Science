# Nghiệm thu luồng thu thập API định kỳ

Ngày kiểm tra 29 tháng 10 năm 2026, macOS ARM64, Python 3.13.7. Luồng mới dùng Tennis API – ATP WTA ITF qua RapidAPI. Chưa có API key nên chưa xác minh response có xác thực trên dịch vụ thật. Người dùng đã chọn hoàn thiện code và hướng dẫn trước.

| Kiểm tra | Kết quả |
| --- | --- |
| Toàn bộ kiểm thử dự án | 80 passed, 0 failures, 0 errors; JUnit ở api_test_results.xml |
| Phân trang đầy đủ | Đã kiểm thử nhiều trang, trang lặp, số trang sai, envelope sai và trang rỗng bất thường |
| Không commit batch thiếu | Lỗi API/quota/phân trang không cập nhật matches hoặc watermark |
| Khóa ổn định | Kiểm thử ID archive bị đánh lại, ID bị tái sử dụng và đảo phía người thắng |
| Cập nhật kết quả | Cùng khóa được cập nhật, stats cũ bị bỏ khi nội dung kết quả thay đổi |
| Stats | Ghép bằng ID người chơi, không theo vị trí; không nhận stats của người khác |
| Quota/retry | Ngân sách chia sẻ giữa các lần chạy trong cùng SQLite, tính cả retry |
| HTTP lỗi | 401/403/429/redirect/JSON sai không được coi là batch rỗng thành công |
| Bảo vệ key | Key chỉ ở header, không ở URL; không ghi lỗi transport chứa key; response echo key được che |
| Export | Tạo snapshot mới rồi đổi CURRENT; lỗi export giữ CURRENT cũ |
| Demo thực thi | 2 trang; 3 trận lưu SQLite, 2 ngoài phạm vi; 2 dòng qua B, 1 cách ly thiếu best_of |
| Demo chạy lại | 0 insert, 0 update, 3 unchanged; không gọi stats lại khi còn trong thời hạn |
| Bàn giao cho C | 14 bảng CSV qua code B hiện có, hợp đồng bảng đi kèm |
| Dữ liệu lịch sử | Chạy lại offline vẫn 27.574 trận và 0 vi phạm; 26 đầu ra khớp SHA256 khi tái lập |
| Lịch launchd | Hai plist được tạo và plutil xác nhận OK; CHƯA kích hoạt |
| Live API | CHƯA chạy; kiểm tra --check dừng vì thiếu RAPIDAPI_KEY như dự kiến |

## Sản phẩm chính

- config/api_batch.json: endpoint, phạm vi, quota và lịch làm mới stats.
- src/data_collection/rapidapi_client.py: HTTP, lưu JSON, checksum và kiểm soát request.
- src/data_collection/api_batch.py và api_store.py: staging, SQLite, upsert và watermark.
- src/preprocessing/rapidapi_adapter.py: chuyển dữ liệu API về schema của B.
- src/analysis/api_export.py: xuất snapshot và bảng thống kê B.
- scripts/run_api_batch.py: CLI thật, demo, kiểm tra cấu hình và export offline.
- scripts/setup_api_schedule.py: tạo/cài/gỡ lịch local.
- tests/test_api_batch.py và tests/fixtures/rapidapi/: kiểm thử cùng fixture nhân tạo có nhãn.
- docs/api_batch.md: hướng dẫn key, chạy thử, đọc đầu ra và vận hành.

## Phần cần làm sau khi có key

Điền key trong .env trên máy, đăng ký đúng gói FREE của sản phẩm, rồi chạy một ngày để xác minh endpoint và độ đầy đủ của response. --check chỉ xác nhận key có mặt, không xác nhận key đúng. Khi batch thật chạy đạt, bật lịch bằng setup_api_schedule.py --install.

Demo không phải dữ liệu tennis thật và không được dùng làm kết luận. Snapshot API hiện để thiếu rank trước giải và thời lượng; các chỉ số tương ứng chưa có mẫu số để phân tích. Không tự nối dữ liệu API và Sackmann khi chưa có bảng ánh xạ định danh. Chi tiết giới hạn và phạm vi sử dụng dữ liệu ở docs/api_batch.md.
