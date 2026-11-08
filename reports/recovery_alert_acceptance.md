# Nghiệm thu phục hồi raw log và cảnh báo Telegram

Mốc nghiệm thu phục hồi/cảnh báo ngày 29 tháng 10 năm 2026, trước lần kích hoạt được ghi nhận trong [live_activation.md](live_activation.md). Tại mốc này các lịch chỉ được tạo, chưa kích hoạt và Telegram chưa được kiểm thử bằng credential thật. Trạng thái hiện tại trên checkout Windows chưa được xác minh. Người dùng chọn nhóm Telegram, token/chat ID cấu hình sau; chấp nhận P1/P2 thử gửi ngay, gộp lặp 30 phút và P3/P4 tổng kết theo lần chạy.

| Hạng mục | Kết quả kiểm chứng |
| --- | --- |
| Toàn bộ kiểm thử | 100 passed, 0 failures, 0 errors |
| Replay raw offline | Dùng 5 response lưu sẵn để dựng lại 3 trận trong kiểm thử; 0 lần gọi Tennis API |
| CLI replay thực thi | 2 trang raw, 3 trận lưu, 2 dòng qua B và 1 cách ly; stats thiếu được công bố rõ |
| Chỉ còn thư mục raw | Đã kiểm thử xóa SQLite gốc và dựng lại bằng manifest; CLI --replay-dir chạy thành công |
| Resume batch lỗi | Kiểm thử giữ trang 1, chỉ lấy trang 2 và stats còn thiếu; không gọi lại trang 1 |
| CLI resume thực thi | 2 cache hit, 0 insert, 0 update, 3 unchanged; giữ database không trùng |
| Toàn vẹn raw | Raw bị sửa hash phải dừng, không tiến watermark hoặc gọi bù trong offline |
| Request quota | Cache hit có audit riêng, không tính vào network budget |
| Log task | JSONL có operation, stage, thời gian, trạng thái, exception và traceback đã che secret |
| P1–P4 và tag | Kiểm thử ưu tiên, tag, success theo run và cảnh báo chất lượng |
| Chống lặp | Lỗi lặp suppressed và có bản gộp sau 30 phút; nâng P2 lên P1 không bị chặn |
| Outbox bền vững | Kiểm thử pending khi thiếu cấu hình, retry_after, dead letter, expiry 24 giờ, giới hạn mỗi flush |
| Telegram lỗi | Lỗi transport không lưu URL chứa token; không làm task dữ liệu thất bại |
| Demo/replay | Không gửi Telegram ngay cả khi có credential giả trong môi trường kiểm thử |
| Pipeline lịch sử | Vẫn 27.574 trận và 0 vi phạm theo quy tắc, 26 đầu ra tái lập khớp SHA256 |
| Notebook B | 10/10 ô code chạy, 0 lỗi, 5 hình |
| Lịch local | 3 plist được plutil xác nhận OK; chỉ tạo, chưa kích hoạt |
| Tin thật và API thật | Chưa kiểm thử qua credential thật; không gửi tin Telegram thật |

## Đầu ra và vận hành

Hướng dẫn: docs/recovery_and_alerts.md. Cấu hình: config/observability.json. Secret điền trên máy trong .env, không gửi vào chat và không nằm trong gói bàn giao.

Log: logs/pipeline.jsonl và logs/runs/OPERATION_ID.jsonl. Outbox: data/monitoring/alerts.sqlite3. Raw được ghi trước xử lý, có SHA256 và run_manifest.json. Cache/resume chỉ dùng chuỗi batch được chỉ định; lượt lấy dữ liệu mới không tự dùng cache cũ.

Lịch bổ sung flush Telegram mỗi 10 phút để retry/gửi bản gộp mà không gọi Tennis API. Khi chưa có token/chat ID, các sự kiện thật được giữ pending trong outbox, còn demo/replay ghi dry_run. Telegram chưa cấu hình không chặn xử lý dữ liệu.

## Giới hạn cần giữ khi diễn giải

Chưa có phép thử xác thực với Telegram hoặc Tennis API thật. Mô phỏng HTTP không chứng minh dịch vụ bên ngoài luôn đáp ứng. Tin có thể trùng sau timeout khi máy chủ đã nhận; không bảo đảm exactly once. Host tắt hoặc job không khởi động cần heartbeat bên ngoài nếu muốn phát hiện tự động. Raw và manifest nên sao lưu cùng nhau, gồm các batch cha được tham chiếu; file mồ côi do kill/mất điện trước ghi index cần kiểm tra thủ công.
