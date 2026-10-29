# Schema chung và nạp tăng dần hằng tuần

Hai nguồn hiện được nạp vào cùng một bộ dữ liệu phân tích có định danh và ý nghĩa thống nhất. Bản khởi tạo có **27.644 trận** gồm 27.574 trận GitHub và 70 trận API, kèm 14 bảng của B. Schema chung phiên bản 2.0.0 giữ đủ 52 cột đầu vào và 77 cột sau xử lý; không làm thay đổi các file raw nguồn.

Điểm đọc chính cho B và C từ đây là **runs/unified/CURRENT.json**, không nối trực tiếp hai CSV nguồn. Dữ liệu GitHub và API riêng vẫn được giữ để kiểm tra, phục hồi và đối chiếu.

## Lịch đang sử dụng

| Lịch theo giờ Việt Nam | Tác vụ |
| --- | --- |
| Hằng ngày 07:10 | Lấy và lưu API raw/SQLite, bổ sung stats và metadata nhánh đấu còn thiếu trong quota |
| Thứ Hai 07:40 | Đối soát API 30 ngày, chuẩn hóa, incremental load vào schema chung và xuất bảng B/C |
| Mỗi 10 phút | Gửi lại/gộp cảnh báo Telegram |

Job tuần `vn.khdl.tennis.weekly` đã đổi sang `run_unified_load.py --collect --refresh-reference`. Đây là một chuỗi tuần tự trong cùng job; không dựa vào khoảng cách giờ giữa hai job riêng. Nếu bước đối soát API thất bại, bước nạp chung dừng và snapshot đã công bố trước đó được giữ.

Máy phải hoạt động và phiên đăng nhập phải sẵn sàng để launchd thực thi. Lịch local không phải dịch vụ server chạy độc lập với máy cá nhân.

## Ý nghĩa thống nhất giữa hai nguồn

| Trường hoặc nhóm | Quy tắc chung |
| --- | --- |
| winner_id, loser_id | ID người chơi nội bộ chung, không nối hai nguồn bằng số ID gốc |
| winner_name, loser_name | Tên của cùng thực thể trong registry; tên nguồn giữ trong raw |
| tourney_id | ID phiên bản giải chung, tiền tố mùa đã giải quyết; khác ID gốc |
| tourney_name | Tên chuỗi giải chuẩn khi có alias đã kiểm chứng; giữ riêng chuỗi chưa liên kết |
| match_num và match_id | Khóa ổn định từ phiên bản giải, vòng và cặp người chơi; không phải thứ tự thời gian |
| round | R256/R128/R64/R32/R16/QF/SF/F/RR, không chứa mã ordinal của API |
| draw_size | Số slot nhánh chính; có thể lớn hơn số người thực đấu vì bye, tương thích cách làm tròn của nguồn GitHub |
| tourney_date | Ngày tham chiếu/bắt đầu giải, không gọi là ngày từng trận |
| season | Mùa từ file GitHub; API dùng năm trận làm fallback được công bố, hoặc mapping mùa rõ ràng |
| surface | Hard/Clay/Grass/Carpet; indoor hard thuộc Hard, chi tiết gốc giữ trong JSON |
| best_of | Giá trị API nếu có, hoặc quy tắc giải đã kiểm chứng đúng năm/phạm vi; không suy từ số set đã chơi |
| score | Tỷ số theo phía người thắng; thống nhất khoảng trắng và marker RET/W/O/DEF |
| rank, minutes và stats thiếu | Giữ null; không điền rank hiện tại, không biến thiếu thành 0 |
| Các thống kê giao bóng | Số đếm cùng ý nghĩa trước khi tính tỷ lệ; mẫu số và trạng thái completed giữ theo quy tắc B |

`data/schemas/tennis_common_schema.json` là hợp đồng chung phiên bản 2.0.0. Schema đầu vào nguồn phiên bản 1.0.0 vẫn tồn tại cho bộ GitHub và kiểm tra raw. Mọi artifact chung được kiểm định theo schema 2.0.0 trước khi công bố.

## Vòng đấu và nhánh đấu

API 9/10/12/8 lần lượt ánh xạ QF/SF/F/RR. Các mã First/Second/Third/Fourth không được đổi cứng thành R32/R16: cùng First có thể là R128 hoặc R32.

Pipeline lấy bảng nhánh chính với `fullBracket=true`, kiểm tra đúng edition, các vị trí đầu liên tục và slot QF/SF/final. Từ số slot đã xác minh mới xác định R32, R64, R128. Bye vẫn tính là slot. Bảng không đủ bằng chứng thì vòng đầu để thiếu và bản ghi được cách ly khỏi bộ chung.

Cache ở data/reference/api_editions.json trỏ về raw có checksum. Mỗi lần đọc đều xác minh hash và tính lại capacity từ raw, không chỉ tin con số trong file metadata. Metadata hiếm thay đổi được tái sử dụng; request mới dùng chung audit và quota với pipeline API. Trong lần triển khai này chỉ thêm 7 request tham chiếu, tổng số request Tennis API trên máy là 30.

Nguồn quy ước: https://docs.tennis-api.com/misc và https://docs.tennis-api.com/tournaments.

## Liên kết người chơi có bằng chứng

File atp_players.csv được tải từ cùng commit GitHub đã ghim, lưu riêng cùng URL/SHA256/giấy phép trong data/reference/github_players_manifest.json. Registry dùng cả tên chuẩn từ danh mục người chơi và alias quan sát được trong các trận lịch sử.

Chỉ tự liên kết khi tên đầy đủ đã chuẩn hóa Unicode/khoảng trắng/dấu câu và IOC xác định đúng một ứng viên. Không dùng fuzzy matching. Hai ID GitHub trùng thực thể chỉ được gộp khi cùng khóa tên đầy đủ/IOC và cùng ngày sinh hợp lệ; DOB thiếu hoặc khác nhau không được coi là bằng chứng trùng.

Một người chơi không liên kết chắc chắn vẫn có ID nội bộ riêng theo nguồn trong vùng số dành riêng, không trùng ID GitHub. Crosswalk ghi method và evidence; pipeline cảnh báo để rà soát trước khi dùng thống kê xuyên nguồn. Matching tên/IOC là bằng chứng được công bố, không phải bảo đảm tuyệt đối; cần kiểm tra thủ công nếu có nghi ngờ đồng danh.

Sửa các trường hợp đã review bằng data/mappings/player_overrides.csv, luôn ghi lý do. Không sửa trực tiếp ID gốc hoặc dữ liệu raw.

## Liên kết giải và mùa giải

config/tournament_aliases.json chứa các alias có nguồn kiểm chứng. Ví dụ European Open chuyển Antwerp sang Brussels và Astana chuyển Almaty. Lyon indoor 2026 liên kết lịch sử Marseille theo thông báo ATP, **không** liên kết với giải Lyon sân đất nện chỉ vì cùng tên thành phố.

Phiên bản giải đối chiếu bằng chuỗi giải, mùa, cấp giải, mặt sân và ngày tham chiếu gần nhau trong 3 ngày. Cùng tên/cùng năm nhưng khác tuần được giữ thành các edition riêng. Không ghép gần đúng theo tên thành phố. API trong năm đã có dữ liệu GitHub nhưng chưa liên kết được edition sẽ được giữ để review thay vì tạo bản sao xuyên nguồn một cách âm thầm.

Giải mới chưa có alias trong năm ngoài phạm vi lịch sử có thể giữ series riêng theo nguồn và được gắn cảnh báo. Muốn nối chuỗi giải qua các năm cần bổ sung alias có bằng chứng.

Giải bắt đầu trong tháng 12 có thể thuộc mùa sau. Khi chỉ có dữ liệu tháng 12 và chưa có bằng chứng mùa, pipeline không tự coi năm lịch là mùa chính thức. Dùng data/mappings/edition_overrides.csv để chỉ định season và/hoặc canonical_edition_id có lý do. Format best_of suy từ quy định cũng phải có năm được review tương ứng.

## Incremental load và xử lý xung đột

SQLite chung ở data/unified/tennis.sqlite3. Mỗi contribution có khóa provider + source_key và fingerprint. Pipeline so nội dung cùng phiên bản quy tắc, mappings, tham chiếu và code chuẩn hóa; chỉ xử lý lại các contribution thay đổi. Nếu đổi policy/schema/code, có thể phải tái kiểm định toàn bộ để không giữ kết quả theo quy tắc cũ.

Fact chung chỉ insert khi có trận mới, update khi trường dữ liệu/lineage thay đổi thực sự và giữ nguyên khi không thay đổi. Đổi tên/vị trí file raw đơn thuần không bị tính là sửa kết quả tennis. Không lọc delta chỉ bằng ngày trận, vì stats/kết quả trận cũ có thể được chỉnh muộn. load_state lưu policy hash và mốc API last_seen_at; bảng loads ghi từng lần commit/publish.

Khi hai nguồn nói về cùng trận, chỉ gộp nếu người thắng/thua, tỷ số, vòng và thể thức tương thích. Mâu thuẫn kết quả được giữ trong match_conflicts và không đưa vào kết quả chung. GitHub được ưu tiên trong vùng lịch sử; chỉ dùng API bổ sung ô tùy chọn còn null, không ghi null đè giá trị đã biết. Bất đồng trường tùy chọn được ghi lại để review, không che mất bằng chứng nguồn.

Không tự xóa dữ liệu chỉ vì một record vắng trong response lần này. Thay đổi định danh/vòng hoặc xóa trận ở nhà cung cấp có thể cần review thủ công; chưa tích hợp feed xóa/merge của nhà cung cấp.

Database commit độc lập bước xuất để lỗi xuất có thể chạy lại từ dữ liệu đã lưu. Snapshot được xây xong, kiểm định, ghi checksum rồi mới đổi CURRENT. Nếu toàn bộ fact không còn hợp lệ thì giữ snapshot đã công bố và báo lỗi, không công bố một bộ rỗng giả thành công. Lượt không có thay đổi nguồn/policy dùng lại snapshot thay vì ghi lại tất cả bảng; CURRENT có last_checked_at_utc để phân biệt thời điểm kiểm tra với thời điểm dữ liệu đổi.

## Đọc dữ liệu cho B và C

```python
from pathlib import Path
import json
import pandas as pd

output = Path('runs/unified')
pointer = json.loads((output/'CURRENT.json').read_text())
snapshot = output/pointer['snapshot']
matches = pd.read_csv(snapshot/'tennis_matches.csv')
trend = pd.read_csv(snapshot/'tables/season_summary.csv')
```

| Artifact | Ý nghĩa |
| --- | --- |
| canonical_input.csv | 52 cột chuẩn chung trước đặc trưng B |
| tennis_matches.csv | 77 cột sau làm sạch và tạo đặc trưng |
| player_matches.csv | Hai phía người chơi cho mỗi trận, dùng ID chung |
| tables/ | 14 bảng phân tích và table_contract.json |
| players.csv, player_crosswalk.csv | ID chung, tên, DOB và ánh xạ nguồn có bằng chứng |
| editions.csv, edition_crosswalk.csv | Phiên bản giải chung và ánh xạ ID nguồn |
| source_records.csv | Trạng thái từng contribution và metadata nguồn |
| match_provenance.jsonl | Các nguồn đóng góp và nguồn dữ liệu của từng trường |
| conflicts.csv | Các trận có kết quả mâu thuẫn cần xử lý |
| coverage_by_source.csv, coverage_by_season.csv | Độ phủ từng nguồn/mùa, không che khoảng trống dữ liệu |
| manifest.json | Version, policy hash, số liệu và checksum |

Trong match_provenance, default_field_source áp dụng cho các giá trị có mặt lấy từ nguồn chính; field_sources chỉ ghi các trường ngoại lệ được bổ sung từ nguồn khác. ID/tên/edition đã chuẩn hóa còn phải truy qua registry/crosswalk và metadata source_records. Giá trị null không được hiểu là đã có dữ liệu từ nguồn mặc định.

## Chạy thủ công và phục hồi

```bash
# Chỉ nạp từ dữ liệu đã lưu, không gọi Tennis API
.venv/bin/python scripts/run_unified_load.py

# Cho phép lấy metadata nhánh đấu còn thiếu trong quota
.venv/bin/python scripts/run_unified_load.py --refresh-reference

# Toàn chuỗi tuần: đối soát API rồi nạp chung
.venv/bin/python scripts/run_unified_load.py --collect --refresh-reference

# Kiểm tra mà không gửi Telegram
.venv/bin/python scripts/run_unified_load.py --dry-notify
```

Nếu xuất chung lỗi, chạy lại lệnh mặc định để dùng lại dữ liệu nguồn đã lưu. Nếu fetch API lỗi, dùng --resume-run hoặc --replay-dir của run_api_batch như hướng dẫn phục hồi. Không sửa raw để ép khớp checksum.

## Giới hạn phân tích và nguồn

Dữ liệu 2026 hiện chỉ có 22–28/10, không phải cả mùa. Chưa backfill khoảng từ đầu năm 2026 đến 21/10. Không so tổng số trận của phần mùa này với trọn mùa 2015–2025 rồi kết luận xu hướng. Ngày thực tế từng trận GitHub không có và vẫn để unknown trong provenance; không lấy ngày giải thay thế. API chưa có rank trước giải/minutes trong adapter nên các chỉ số liên quan vẫn thiếu, không bịa ra để đủ format.

Nguồn GitHub vẫn phải ghi công Jeff Sackmann / Tennis Abstract và giữ điều kiện CC BY-NC-SA 4.0. Dữ liệu API theo quyền sử dụng của nhà cung cấp, không tự động mang giấy phép của GitHub. Credential và dữ liệu API thật không nằm trong gói source công khai.
