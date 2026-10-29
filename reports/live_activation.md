# Kích hoạt flow dữ liệu thật và lịch tự động

Đã kích hoạt ngày 29 tháng 10 năm 2026, timezone máy +07. API đã xác thực, bot Telegram gửi cá nhân đã nhận xác nhận gửi; cả ba LaunchAgent đã được nạp. User cần giữ máy hoạt động và phiên đăng nhập có sẵn để lịch local chạy.

| Hạng mục | Kết quả |
| --- | --- |
| Khoảng ngày thu thập | 2026-10-22 đến 2026-10-28, theo UTC |
| Run thu thập thật | baba07d90f4e4d90b837f4006192aad3 |
| Response kết quả | 3 trang, 1.260 dòng gốc, lọc giữ 70 trận |
| Dữ liệu qua B | 70 trận, 0 cách ly, 0 vi phạm, 14 bảng thống kê |
| Tình trạng trận | 66 completed, 2 retired, 2 walkover |
| Stats đã lấy | 20 trận; 48 ứng viên còn chờ do cap 20/lượt |
| Request Tennis API dùng | 23 gồm 3 trang kết quả và 20 stats |
| Khắc phục schema | best_of trống được bổ sung theo quy định 2026 có nguồn, không sửa raw |
| Kiểm thử sau sửa | 112 passed, 0 failures, 0 errors |
| Kiểm tra launchd | Job Telegram exit 0; job xuất dữ liệu end-to-end qua launchd exit 0 |
| Telegram | Summary của lượt export qua launchd được xác nhận sent |
| Pipeline lịch sử | Vẫn 27.574 trận; 26 artifact tái lập khớp SHA256 |

## Lịch đang hoạt động

| Job | Lịch giờ Việt Nam | Công việc |
| --- | --- | --- |
| vn.khdl.tennis.daily | 07:10 hằng ngày | Lấy lại 7 ngày UTC đã kết thúc, tiếp tục stats trong ngân sách |
| vn.khdl.tennis.weekly | Thứ Hai 07:40 | Đối soát 30 ngày, chia sẻ ngân sách ngày |
| vn.khdl.tennis.alerts | Mỗi 10 phút | Retry Telegram, gửi digest đã đến hạn, không gọi Tennis API |

Các job hiện có thể ở trạng thái not running giữa hai lượt; loaded là đã được hệ điều hành lập lịch, không phải tác vụ cần chạy liên tục. Lượt thu thập tiếp theo dự kiến 07:10 ngày 30 tháng 10 năm 2026 khi máy có thể thực thi lịch.

## Dữ liệu hiện tại

CURRENT: runs/api/CURRENT.json.

Snapshot được nghiệm thu: `snapshots/20261029T041250-774d66e0`.

Raw: data/api/raw/baba07d90f4e4d90b837f4006192aad3/, có run_manifest.json và checksum. Database: data/api/tennis.sqlite3. Các bảng: runs/api/snapshots/20261029T041250-774d66e0/tables/. Log theo operation ở logs/runs/; log lịch ở logs/vn.khdl.tennis.*.log.

## Điều chỉnh sau lần gọi thật

API trả best_of=null trên toàn bộ 70 trận. Phiên bản ban đầu cách ly đúng theo schema. Đã kiểm tra quy định ATP 2026 mục 1.02 B và ATP Finals cùng Grand Slam 2026 mục Number of Sets: main draw đơn nam cấp tour, Masters và Finals là best-of-3; Grand Slam là best-of-5.

config/tennis_format_rules.json ghi phiên bản, năm áp dụng, cấp giải và nguồn. Chỉ bổ sung khi API không có giá trị; không sửa giá trị đã có, không suy từ số set đã chơi, không áp dụng cho qualifying/đôi/giải ngoài phạm vi. provenance.csv ghi best_of_source và best_of_reference cho từng dòng; export_manifest.json có toàn bộ cấu hình quy tắc. Nguồn:

- https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook_31mar26.pdf
- https://www.itftennis.com/media/5986/grand-slam-rulebook-2026-f2.pdf

Cần rà soát quy tắc khi sang năm 2027: nếu best_of vẫn thiếu mà năm không nằm trong cấu hình đã kiểm chứng, hệ thống giữ thiếu và cảnh báo/cách ly, không áp dụng quy định cũ âm thầm. Lượt xử lý lại dùng --export-only trên SQLite và raw có sẵn, không tốn request mới.

## Giới hạn vận hành

Stats hiện mới phủ 20 trận và sẽ bổ sung theo lượt tiếp theo; không tuyên bố đủ thống kê cho cả 70 trận. Adapter hiện không lấy rank trước giải và thời lượng nên các chỉ số upset/thời lượng trên snapshot API không có mẫu số hợp lệ. Dữ liệu lịch sử vẫn phân tích riêng, không tự nối ID giữa nhà cung cấp. Lịch local không phải dịch vụ chạy 24/7 khi máy tắt; raw, watermark và cơ chế lấy bù vẫn được giữ.

Credential nằm trong .env trên máy; không ghi token hoặc chat ID vào báo cáo này.
