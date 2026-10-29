# Nghiệm thu schema chung và incremental load

Ngày kiểm tra: 29/10/2026, giờ Việt Nam. Số liệu máy đọc được lưu tại [unified_acceptance.json](unified_acceptance.json).

## Kết quả đã kiểm tra

| Hạng mục | Kết quả |
| --- | --- |
| Dữ liệu chung | 27.644 trận: GitHub 27.574, API 70 |
| Hợp đồng | Schema 2.0.0; 52 cột chuẩn đầu vào, 77 cột sau xử lý |
| Kiểm định schema | Không có lỗi ở cả hai CSV chung |
| Khóa trận trùng | 0 |
| Liên kết API | 80 người chơi theo tên đầy đủ/IOC duy nhất; 5 edition theo alias đã review |
| Chất lượng lần nạp gần nhất | 0 contribution cách ly, 0 xung đột kết quả |
| Chạy lại cùng dữ liệu | 0 insert, 0 update, 27.644 unchanged; dùng lại snapshot |
| Đầu ra B | 14 bảng, kèm coverage và provenance |
| Toàn vẹn snapshot | 27 checksum khớp manifest |
| Bộ kiểm thử | 143 passed, 0 failed, 0 error |
| Tái lập GitHub | 11 raw file xác minh; 26 artifact khớp byte-for-byte |

Bộ kiểm thử bao gồm trường hợp hai nguồn dùng ID số trùng cho người khác nhau, tên đồng danh, gộp ID có bằng chứng ngày sinh, vòng đấu phụ thuộc nhánh đấu, mùa giải override, hai edition khác tuần, null không ghi đè giá trị đã biết, bổ sung stats cập nhật đúng trận và xung đột kết quả được cách ly. Đổi đường dẫn raw đơn thuần không làm tăng số business update.

## Vận hành

Job `vn.khdl.tennis.weekly` đã được nạp vào launchd: **Thứ Hai 07:40**, chạy `scripts/run_unified_load.py --collect --refresh-reference`. Các job lấy raw hằng ngày 07:10 và gửi lại cảnh báo mỗi 10 phút vẫn được giữ.

Đã thử chạy loader bằng launchd với dữ liệu API thật đã lưu: exit 0, không phát sinh HTTP request, dùng lại snapshot. Job thử nghiệm đã được gỡ. Không chạy lại thủ công toàn chuỗi đối soát API 30 ngày trong lần nghiệm thu này để giữ quota; lịch tuần đã được cấu hình, còn bước common load đã chạy thực tế trên dữ liệu đang có.

Snapshot hiện hành được tra qua [CURRENT.json](../runs/unified/CURRENT.json). Không cố định đường dẫn snapshot trong notebook hoặc phần C. Hướng dẫn lệnh chạy, mapping và phục hồi tại [unified_schema.md](../docs/unified_schema.md).

## Giới hạn hiện tại

- API năm 2026 hiện chỉ phủ 22–28/10; chưa backfill từ đầu năm đến 21/10. Không diễn giải như trọn mùa.
- Matching tên/IOC là bằng chứng được ghi nhận, cần review nếu phát hiện đồng danh hoặc nguồn đổi tên/ID.
- Trường API chưa cung cấp giữ null. Không suy rank trước giải, minutes hoặc thống kê còn thiếu để lấp ô.
- Lịch chạy trên Mac cần máy và phiên đăng nhập sẵn sàng; đây chưa phải lịch chạy trên server độc lập.

Raw, log tác vụ, registry/crosswalk, checksum, hàng cách ly và xung đột được giữ để truy vết. Credential không đưa vào báo cáo.
