# Phục hồi từ raw và theo dõi pipeline qua Telegram

Đã bổ sung theo yêu cầu: raw làm điểm phục hồi, log theo lần chạy và công đoạn, cảnh báo gửi riêng từ bot tới cá nhân bạn, ưu tiên P1–P4, chống lặp và hàng đợi gửi tin bền vững. Token và chat ID cá nhân đã được cấu hình trên máy; đã gửi tin thật và kích hoạt lịch ngày 29 tháng 10 năm 2026. Xem reports/live_activation.md; các kiểm thử mô phỏng được ghi ở báo cáo nghiệm thu phiên bản trước.

## Chọn cách chạy lại để tiết kiệm API

| Trường hợp | Lệnh | Có gọi Tennis API không |
| --- | --- | --- |
| Database đã cập nhật xong nhưng xuất bảng lỗi | --export-only | Không |
| Muốn chạy lại một batch hoàn toàn từ raw | --replay-run RUN_ID | Không, xuất sang vùng riêng |
| Còn raw nhưng không còn SQLite gốc | --replay-dir RAW_RUN_DIRECTORY | Không, dựng lại index từ manifest |
| Batch gọi API bị lỗi giữa chừng | --resume-run RUN_ID | Chỉ gọi phần chưa có raw HTTP 200 hợp lệ |
| Muốn lấy cập nhật mới từ nhà cung cấp | Chạy bình thường | Có, lấy dữ liệu mới; không dùng cache cũ ngầm định |

```bash
# Xem ID và trạng thái các batch thật
.venv/bin/python scripts/run_api_batch.py --list-runs

# Chạy lại bước B từ database, không tốn request
.venv/bin/python scripts/run_api_batch.py --export-only

# Chạy lại raw của một batch vào vùng cô lập
.venv/bin/python scripts/run_api_batch.py --replay-run RUN_ID

# Phục hồi chỉ từ thư mục raw và run_manifest.json
.venv/bin/python scripts/run_api_batch.py --replay-dir data/api/raw/RUN_ID

# Tiếp tục batch lỗi, dùng lại raw đã có
.venv/bin/python scripts/run_api_batch.py --resume-run RUN_ID
```

Thêm --demo khi dùng --list-runs, --replay-run hoặc --resume-run với database demo. --replay-dir tự đọc thư mục bạn chỉ định và luôn là offline. Không cần RapidAPI key để replay/export; resume chỉ cần key khi thực sự phải lấy thêm dữ liệu chưa có.

## Raw là ranh giới phục hồi

Mỗi response HTTP được lưu và fsync trước khi parse JSON, kiểm định, chuẩn hóa hoặc cập nhật trận. Các lần retry có file riêng, không ghi đè response trước. Metadata có endpoint, tham số, status, thời điểm UTC, SHA256 và việc đã che credential nếu nhà cung cấp phản hồi lại key. Request headers và token không được ghi vào raw metadata.

Sau mỗi batch, kể cả batch thất bại có kiểm soát, `raw/RUN_ID/run_manifest.json` liệt kê khoảng ngày, cấu hình, các response, hash và các file raw được dùng lại từ lần trước. Cache hit cũng được ghi vào SQLite riêng và không tính như một lần gọi mạng. Manifest có đường dẫn tương đối để có thể chép raw sang vị trí khác.

Replay kiểm tra checksum trước khi dùng mỗi response. Thiếu trang kết quả, HTTP 200 chứa JSON sai hoặc checksum sai đều làm dừng; không âm thầm gọi API để bù trong chế độ offline. Nếu thiếu stats tùy chọn, replay vẫn xuất được kết quả trận, đồng thời ghi `stats_missing_raw`/`stats_deferred` để công bố độ phủ còn thiếu.

--replay-dir không cần database gốc: nó dựng index tạm từ raw và manifest. Nếu manifest có cache_hits tham chiếu sang batch trước, cần sao lưu **toàn bộ cây raw** để giữ các file được tham chiếu, không chỉ chép một thư mục con. Không tự xóa raw khi retry, không dùng dữ liệu demo làm dữ liệu thật.

Replay xuất vào `runs/api_replay/`, không ghi lùi kết quả mới trong database thật. Resume cập nhật database đang dùng, nhưng bị chặn nếu đã có batch mới hơn thành công; khi đó dùng replay cô lập để đối chiếu. Cache chỉ lấy từ batch nguồn và chuỗi batch cha của nó, không tìm dữ liệu cũ bất kỳ có cùng endpoint. Lượt chạy bình thường luôn đi lấy kết quả mới để không bỏ sót chỉnh sửa từ nhà cung cấp.

Giới hạn: nếu tiến trình bị kill hoặc máy mất điện đúng lúc ghi file/index, manifest có thể chưa hoàn thành. Khi còn SQLite, audit request vẫn hỗ trợ truy vết các response đã được ghi nhận; file mồ côi chưa có index cần kiểm tra thủ công. Fsync raw không thay thế sao lưu ngoài máy.

## Log và mã truy vết

Log JSON Lines gồm timestamp_utc, operation_id, parent_operation_id nếu có, pipeline, mode, stage, event, priority và số liệu/timing của công đoạn. Lỗi có loại exception, thông điệp đã che bí mật và traceback. Không đưa payload từng trận vào log hay Telegram.

| Vị trí | Nội dung |
| --- | --- |
| logs/pipeline.jsonl | Log tổng hợp, xoay ở 10 MB, giữ 5 bản cũ |
| logs/runs/OPERATION_ID.jsonl | Log riêng một lần chạy, không mất khi log tổng hợp xoay |
| data/api/tennis.sqlite3 | batch_runs, requests, cache_hits và trạng thái dữ liệu |
| data/monitoring/alerts.sqlite3 | Trạng thái gửi, retry, suppression và dead letter của cảnh báo |

operation_id của CLI API cũng là run_id của batch thu thập để tìm thẳng raw và database. Export-only có operation_id riêng vì không tạo batch thu thập. Các công đoạn được ghi gồm discovery, enrichment, database_commit, normalization, validation, analysis và snapshot_export.

Pipeline lịch sử, kiểm tra tái lập và thực thi notebook cũng có log/thông báo. Tiến trình con của kiểm tra tái lập vẫn ghi log nhưng không gửi Telegram riêng; kết quả được báo bởi tiến trình cha để tránh tin trùng.

```bash
# Tìm toàn bộ log của một lần chạy
rg 'OPERATION_ID' logs/pipeline.jsonl

# Mở log đầy đủ, kể cả khi log tổng hợp đã xoay
cat logs/runs/OPERATION_ID.jsonl

# Xem số cảnh báo theo ưu tiên và trạng thái, không gọi Telegram
.venv/bin/python scripts/telegram_alerts.py --status
```

Các file per-run, raw và snapshot chưa tự xóa. Khi cần quản lý dung lượng, nên sao lưu và kiểm tra khả năng phục hồi trước khi đặt thời hạn giữ; không xóa raw vẫn đang được manifest tham chiếu. Log tổng hợp là tiện ích tra cứu, log riêng mỗi operation là bằng chứng chính khi các tiến trình chạy đồng thời.

## Mức ưu tiên và chống quá tải tin nhắn

| Ưu tiên | Ý nghĩa | Ví dụ | Cách gửi |
| --- | --- | --- | --- |
| P1 Critical | Toàn vẹn dữ liệu hoặc bất biến bị phá vỡ | Raw checksum sai, dữ liệu hỏng, assertion kiểm tra thất bại | Thử gửi ngay, có âm báo |
| P2 Error | Công đoạn bị chặn hoặc chất lượng nghiêm trọng | Auth/quota/lỗi mạng hết retry, task lỗi; tỷ lệ cách ly từ 50% | Thử gửi ngay, có âm báo |
| P3 Warning | Chạy xong nhưng có hạn chế dữ liệu | Có dòng cách ly dưới 50%, ô tùy chọn sai, stats còn chờ | Gộp trong một bản tổng kết lần chạy, gửi im lặng |
| P4 Info | Lần chạy hoàn tất không có cảnh báo | Các công đoạn thành công | Một bản tổng kết lần chạy, gửi im lặng |

Cảnh báo hiển thị tiếng Việt: kết quả, số trận/bảng, việc cần làm và giờ Việt Nam. Tag ngắn như #P2 #API, #P1 #DuLieu hoặc #P4 #KetQua giúp tìm nhanh. Mã tra cứu rút gọn 8 ký tự nằm cuối tin; full operation_id, mã lỗi, JSON và traceback được giữ trong log/outbox. Có thể dùng rg với mã rút gọn để tìm log. Cấu hình ở `config/observability.json`; muốn chỉ nhận lỗi/cảnh báo thì đặt notify_success=false. Cảnh báo dữ liệu vẫn được tổng kết dù tắt tin thành công.

Lỗi trùng cùng pipeline/công đoạn/mã lỗi/mức ưu tiên/người nhận được gộp trong 30 phút. Mọi lần xảy ra vẫn lưu trong outbox với trạng thái suppressed. Hết 30 phút, lần flush kế tiếp tạo một bản gộp kèm số lần lặp. P1 không bị che bởi cảnh báo P2 trước đó vì ưu tiên khác tạo nhóm khác. Thành công của các lần chạy khác nhau không bị gộp mất.

## Cấu hình Telegram cá nhân

1. Tạo bot bằng @BotFather trong Telegram, lưu token vào file .env trên máy.
2. Mở chat riêng với bot và bấm Start hoặc gửi /start. Không cần tạo nhóm hay thêm bot vào nhóm.
3. Lấy chat ID cá nhân bằng getUpdates của chính bot sau khi gửi /start. Chọn bản ghi có message.chat.type=private và lấy message.chat.id của đúng bạn; không tự chọn người nhận khi có nhiều chat. Không đăng token vào URL công khai, log hoặc ảnh chụp.
4. Điền các biến sau vào .env, các placeholder đã được thêm sẵn:

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Chat ID cá nhân là số dương. Cấu hình recipient_type=private sẽ chặn ID nhóm/kênh để tránh gửi nhầm; muốn đổi về nhóm phải thay cấu hình một cách chủ động. Đọc hướng dẫn chính thức khi cấu hình: https://core.telegram.org/bots#how-do-i-create-a-bot và https://core.telegram.org/bots/api#getupdates. Nếu bot đã dùng webhook, getUpdates có thể không dùng đồng thời được; không tự xóa webhook đang phục vụ ứng dụng khác để lấy ID.

Sau khi cấu hình, chủ động gửi một tin kiểm tra:

```bash
.venv/bin/python scripts/telegram_alerts.py --test
```

CLI hiển thị trạng thái của tin kiểm tra. Chỉ `sent` mới là đã nhận xác nhận của Telegram; pending/retry/dead_letter không có nghĩa là gửi thành công. Khi chưa có token/ID, pipeline vẫn chạy, cảnh báo lưu cục bộ và ghi delivery=not_configured. Demo và replay luôn ở chế độ dry_run, không gửi ra Telegram ngay cả khi có credential trên máy.

## Khi Telegram lỗi

Outbox được lưu tách khỏi transaction dữ liệu. Lỗi mạng Telegram không rollback kết quả trận và không khiến job gọi lại Tennis API. Tin lỗi chờ retry ở lần flush kế tiếp; HTTP 429 tuân thủ retry_after; lỗi 400/401/403/404 vào dead_letter để tránh gửi vô hạn. Tối đa 8 lần thử, mỗi flush tối đa 5 tin, tin chờ quá 24 giờ bị expired. Không tạo cảnh báo Telegram mới cho lỗi gửi Telegram để tránh vòng lặp.

Sau khi sửa token/quyền/người nhận, kiểm tra --status. Dead letter không tự gửi lại; gửi --test để xác minh cấu hình mới và để sự kiện mới đi qua luồng bình thường. Trạng thái retry được xử lý bằng:

```bash
.venv/bin/python scripts/telegram_alerts.py --flush
```

Cơ chế gửi là best effort với retry bền vững, không bảo đảm exactly once: nếu Telegram nhận tin nhưng kết nối timeout trước khi client đọc phản hồi, lần retry có thể tạo bản sao. Tin có alert ID và operation ID để nhận biết. Nếu host tắt hoặc job không khởi động thì code trên host không thể tự báo; cần dịch vụ heartbeat bên ngoài nếu muốn giám sát trường hợp này.

## Lịch chạy và trạng thái triển khai

setup_api_schedule.py tạo thêm job `vn.khdl.tennis.alerts` chạy flush mỗi 10 phút để không phải chờ tới batch ngày hôm sau. Hai lịch thu thập/đối soát vẫn giữ nguyên. Cả ba lịch đã được cài sau khi xác minh credential và chạy batch thật. Trạng thái launchd được ghi ở reports/live_activation.md.

```bash
# Tạo lại 3 plist để xem, chưa bật lịch
.venv/bin/python scripts/setup_api_schedule.py

# Sau khi đã cấu hình và kiểm tra API/Telegram
.venv/bin/python scripts/setup_api_schedule.py --install
```

Không có tin Telegram thật được gửi trong quá trình kiểm thử; phần gửi tin được kiểm thử bằng mock để kiểm tra retry, gộp, ưu tiên và xử lý lỗi mà không phát sinh thông báo cho người khác.

## Mẫu thông báo dễ đọc

Mẫu đang áp dụng từ ngày 29 tháng 10 năm 2026:

```text
✅ ĐÃ XUẤT BẢNG PHÂN TÍCH TENNIS
• Đủ điều kiện phân tích: 70 trận; đã tạo 14 bảng.

Không cần thao tác thêm.
```

Tin có cảnh báo ghi số trận còn chờ hoặc bị tạm giữ và phân biệt việc hệ thống tự tiếp tục với việc bạn cần kiểm tra. Toàn bộ trận bị cách ly không được trình bày như thành công phân tích. Cả tin mới lẫn summary cũ còn nằm trong hàng đợi đều được render theo cách dễ đọc; không gửi lại các tin cũ đã sent. Các lịch tự nạp code mới ở lượt chạy kế tiếp, không cần cài lại lịch.
