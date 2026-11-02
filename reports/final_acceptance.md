# Nghiệm thu cuối — phần C và trạng thái hiện tại

## Cập nhật ngày 02/11/2026

Môi trường: Windows, Python 3.14.3, virtual environment `.venv`. Nhánh local: `c`. Lần cập nhật này chạy pipeline historical offline và đối chiếu manifest; không chạy lại test suite.

| Kiểm tra | Kết quả lần này |
| --- | --- |
| Pipeline historical offline | Pass: 30.616 dòng nguồn, 3.042 ngoài phạm vi, 27.574 giữ lại, 0 lỗi sau xử lý, 14 bảng |
| Tái lập SHA-256 | Pass: 11/11 raw input, 41/41 source/schema và 26/26 output artifact khớp manifest; 0 mismatch |
| Cách xác minh | Chạy `run_pipeline.py --offline` vào output directory mới đã tạo sẵn trong workspace; so sánh input, source-code và output manifest |
| Script `verify_reproducibility.py` | Chưa chạy trọn trong sandbox: Windows từ chối quyền tạo thư mục con trong temp. Phép chạy pipeline độc lập và so manifest nêu trên đã hoàn tất thành công |
| Full test suite | Không chạy lại ngày 02/11. Báo cáo nghiệm thu 01/11 ghi 158 passed trên Python 3.13.17 |
| Notebook/biểu đồ C | Có sẵn trong repo; không thực thi lại notebook hoặc export hình trong lần cập nhật này |

Lệnh pipeline đã chạy:

```powershell
.\.venv\Scripts\python.exe scripts\run_pipeline.py --offline
```

Kết quả checksum được lưu tại `reports/reproducibility.json`. Các phép so sánh dùng cùng raw cache ghim phiên bản và không gọi mạng/API.

## Bằng chứng nghiệm thu trước đó

Ngày 01/11/2026, báo cáo trước ghi cài dependency, 158 test pass, export 6 PNG/6 SVG, thực thi notebook C và pipeline sample thành công. Đây là kết quả của môi trường Python 3.13.17 và không được xem là lần chạy test ngày 02/11.

Các báo cáo cũ về 49/80/112/143 test thuộc các mốc và cấu hình trước đó. Dùng 158 pass làm kết quả test gần nhất đã được ghi nhận; lần rà soát hiện tại chỉ xác minh lại pipeline historical và checksum.

## Trạng thái vận hành và Git

- Báo cáo kích hoạt ghi nhận ba lịch `launchd` đã được cài trên máy macOS ngày 29/10/2026. Trạng thái chạy hiện thời chưa được xác minh trên checkout Windows này.
- Nhánh `c` đã được tạo local. Working tree còn thay đổi chưa commit; chưa có xác nhận push hoặc pull request.
- Dữ liệu API 2026 và lịch vận hành là phần mở rộng độc lập; không gộp vào kết quả historical của phần C.

## Giới hạn diễn giải dữ liệu

Thời lượng mùa 2015 có độ phủ thấp; các giá trị 987 và 1.146 phút vẫn được giữ với cờ review. Tỷ lệ và so sánh nhóm dùng mẫu số riêng theo từng metric. Phân tích mô tả không chứng minh quan hệ nhân quả. Dữ liệu API 2026 hiện chỉ phủ một khoảng ngày trong tháng 10, không phải trọn mùa.
