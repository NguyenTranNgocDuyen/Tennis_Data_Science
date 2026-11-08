# Nghiệm thu cuối — phần C và trạng thái hiện tại

## Kiểm thử mới nhất ngày 07/11/2026

Môi trường: Windows, Python 3.14.3, virtual environment `.venv`. Chạy toàn bộ bộ test offline bằng lệnh:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-current-audit -p no:cacheprovider --junitxml reports\test_results_20261107.xml
```

Kết quả: **158 passed, 0 failed, 0 errors** trong 11,16 giây. JUnit XML được lưu tại `reports/test_results_20261107.xml`. Bộ test dùng fixture và không xác minh API, Telegram hoặc lịch launchd thật.

Ngày 07/11/2026, ba cell code của notebook C được thực thi tuần tự trong một tiến trình Python, với `FIGURES` trỏ tới thư mục tạm để tránh ghi đè artifact. Các bảng được nạp thành công; cell hiển thị kích thước cho kết quả 6 bảng và cell xuất hình tạo đủ 6 PNG/6 SVG. Sáu PNG mới khớp pixel với PNG đang lưu. Đã sửa output cell 3 trong notebook để khớp với biểu thức `frame.shape`. Jupyter kernel không khởi động được trong môi trường này (`win32api` thiếu và thao tác connection file bị từ chối quyền), nên chưa xác minh thực thi notebook bằng Jupyter end-to-end.

Sáu SVG đã được tái xuất. Diff gồm ngày tạo metadata đổi từ 01/11 sang 02/11/2026, ID clip path được tạo lại, cách xuống dòng trong dữ liệu path và kích thước tệp thay đổi; do đó không chỉ là bỏ trailing whitespace. Đây là thay đổi artifact, không phải thay đổi logic vẽ. Các SVG cũ/mới parse được dưới dạng XML, và sáu PNG xuất mới khớp pixel với PNG đã lưu. Chưa có so sánh render trực quan riêng giữa từng cặp SVG cũ/mới, nên không kết luận rằng khác biệt SVG chỉ ảnh hưởng metadata/cách biểu diễn.

Môi trường kiểm tra hiện tại là Windows nên không thể đọc trạng thái `launchd` trên macOS. Trạng thái hiện tại vẫn là **chưa xác minh**; bằng chứng kích hoạt ngày 29/10/2026 chỉ mô tả trạng thái tại thời điểm đó. Không gọi API hoặc Telegram trong lần kiểm tra này. Jupyter kernel không khởi động được do thiếu `win32api` và lỗi quyền `PermissionError: [WinError 5] Access is denied`; phép chạy thay thế tuần tự các cell bằng tiến trình Python thường được mô tả ở trên, không được xem là thực thi notebook end-to-end.

## Kiểm chứng bổ sung ngày 08/11/2026

Lần kiểm tra này dựa trên HEAD `7ede4e5` cộng với các thay đổi chưa commit trong working tree, trên Windows, Python 3.14.3, pandas 3.0.6, NumPy 2.3.5, requests 2.31.0 và jsonschema 4.26.0. Đây là phiên bản working tree, không phải commit bàn giao.

| Kiểm tra | Kết quả |
| --- | --- |
| Full test suite | **163 passed, 0 failed**; gồm 5 test mới cho cô lập output và kiểm tra quyền sở hữu plist |
| Pipeline historical offline | Pass: 30.616 raw, 3.042 ngoài phạm vi, 27.574 giữ lại, 0 quarantine, 0 lỗi sau làm sạch, 14 bảng |
| Vùng output | `runs/historical-audit-20261108/`; pipeline và log observer được ghi trong vùng này |
| Raw input | 11/11 checksum trùng manifest hiện có |
| Artifact so với `reports/run_manifest.json` hiện có | 25/26 checksum trùng; một khác biệt ở `processed_contract.json`: kiểu boolean suy ra là `boolean` ở môi trường hiện tại và `bool[pyarrow]` trong manifest cũ. Các bảng phân tích còn lại khớp checksum |
| Tác động ngoài output | File sample và provenance manifest không bị ghi lại; chế độ offline chỉ đọc manifest/raw. Không gọi mạng/API, Telegram hoặc lịch |

Kết quả test dùng Python 3.14.3 toàn cục trong phiên này; không dùng `.env`. Lần chạy pipeline và test gắn với working tree chưa commit nêu trên. Không thực thi notebook trong lần kiểm tra này.

Notebook C không được chạy lại: môi trường hiện tại không có `jupyter`, `nbformat`, `nbclient`, `ipykernel` hoặc `jupyter_client`. Các output/biểu đồ lưu sẵn là artifact hiện có, không phải kết quả của lần chạy ngày 08/11. Đã rà source/output notebook cho các mẫu đường dẫn máy cá nhân thường gặp; không tìm thấy kết quả khớp, nhưng chưa xác minh lại từng output cell bằng thực thi.

### Đối chiếu bổ sung từ transcript chạy ngày 08/11/2026

Các lệnh và kết quả dưới đây do người dùng cung cấp trong transcript PowerShell; sau đó artifact trong ba thư mục `runs/` được kiểm tra chỉ đọc. Các thư mục này bị Git ignore, không được checkout mới mang theo.

| Hạng mục | Bằng chứng và kết quả đối chiếu |
| --- | --- |
| Notebook C | Bản sao tại `runs/notebook-check-20261108-142925/`: 3/3 cell chạy, execution count 1–3, 9 outputs, gồm 6 PNG display, 0 lỗi. Có 6 PNG và 6 SVG trong thư mục hình tạm. Transcript ghi hash notebook gốc và hình trong `reports/figures/` không đổi. |
| Source notebook | Notebook gốc và bản thực thi có source giống nhau; bản chuẩn bị chỉ đổi `FIGURES` ở cell 2 để trỏ vào thư mục tạm. Notebook gốc không có mẫu đường dẫn cá nhân trong lần quét; bản thực thi tạm có 12 kết quả khớp đường dẫn trong output cell do hiển thị đường dẫn các hình tạm, nên không đưa bản thực thi đó vào gói bàn giao nguyên trạng. |
| Hình mới so với `reports/figures/` | 6/6 PNG byte-identical. SHA-256 của cả 6 SVG khác; chưa so sánh render SVG trực quan nên không kết luận hai nhóm SVG tương đương về hình ảnh. |
| Pipeline historical offline | Output tại `runs/historical-20261108-142948/`: 30.616 raw, 3.042 ngoài phạm vi, 27.574 giữ lại, 0 quarantine, 0 post-clean validation issue, 14 bảng. Run manifest: 11/11 raw input, 41/41 source/schema và 26/26 output checksum khớp; 14/14 bảng CSV khớp byte với `reports/tables/`. Cả 26 output checksum cũng khớp `reports/run_manifest.json` hiện có. |
| Pipeline sample | Output tại `runs/sample-20261108-143033/`: 127 đầu vào, 125 giữ lại, 2 duplicate có chủ đích bị loại, 14 bảng. Manifest xác nhận 1/1 input, 41/41 source/schema và 26/26 output checksum khớp. |
| Môi trường | Run manifest ghi Python 3.14.3, pandas 3.1.0, NumPy 2.5.4, requests 2.34.2, jsonschema 4.26.0. Các phiên bản thư viện khớp lock hiện có; phiên bản Python khác ghi chú môi trường thử nghiệm Python 3.13.7 trong dependency lock. |
| Cảnh báo kernel | Transcript ghi cảnh báo ZMQ/Proactor và TCP kernel không mã hóa; không có execution error. Kết quả chỉ xác nhận lần chạy cục bộ này, không xác nhận cấu hình kernel dùng qua mạng là an toàn. |

Các run manifest gắn checksum với source/schema trong working tree tại thời điểm chạy; HEAD khi kiểm tra là `7ede4e5`, còn thay đổi chưa commit. Lần đối chiếu này không chạy lại test, notebook hoặc pipeline và không gọi dịch vụ. Không dùng kết quả này để kết luận API, unified snapshot, Telegram hoặc `launchd` đang hoạt động.

## Cập nhật ngày 02/11/2026

Môi trường: Windows, Python 3.14.3, virtual environment `.venv`. Nhánh local: `c`. Lần cập nhật này chạy pipeline historical offline và đối chiếu manifest; không chạy lại test suite.

| Kiểm tra | Kết quả lần này |
| --- | --- |
| Pipeline historical offline | Pass: 30.616 dòng nguồn, 3.042 ngoài phạm vi, 27.574 giữ lại, 0 lỗi sau xử lý, 14 bảng |
| Tái lập SHA-256 | Pass: 11/11 raw input, 41/41 source/schema và 26/26 output artifact khớp manifest; 0 mismatch |
| Cách xác minh | Chạy `run_pipeline.py --offline` vào output directory mới đã tạo sẵn trong workspace; so sánh input, source-code và output manifest |
| Script `verify_reproducibility.py` | Chưa chạy trọn trong sandbox: Windows từ chối quyền tạo thư mục con trong temp. Phép chạy pipeline độc lập và so manifest nêu trên đã hoàn tất thành công |
| Full test suite | Không chạy lại ngày 02/11. Báo cáo nghiệm thu 01/11 ghi 158 passed trên Python 3.13.17; lần chạy mới hơn ngày 07/11 được ghi ở đầu tài liệu |
| Notebook/biểu đồ C | Có sẵn trong repo; không thực thi lại notebook hoặc export hình trong lần cập nhật này |

Lệnh pipeline đã chạy:

```powershell
.\.venv\Scripts\python.exe scripts\run_pipeline.py --offline
```

Kết quả checksum được lưu tại `reports/reproducibility.json`. Các phép so sánh dùng cùng raw cache ghim phiên bản và không gọi mạng/API.

## Bằng chứng nghiệm thu trước đó

Ngày 01/11/2026, báo cáo trước ghi cài dependency, 158 test pass, export 6 PNG/6 SVG, thực thi notebook C và pipeline sample thành công. Đây là kết quả của môi trường Python 3.13.17. Lần chạy test mới ngày 07/11 cũng có 158 test pass trên Python 3.14.3; lần notebook C cùng ngày không khởi động được do lỗi quyền Jupyter nêu trên.

Các báo cáo cũ về 49/80/112/143 test thuộc các mốc và cấu hình trước đó. Hai mốc 158 pass ngày 01/11 và 07/11 có môi trường riêng; dùng XML ngày 07/11 làm bằng chứng máy đọc được mới nhất.

## Trạng thái vận hành và Git

- Báo cáo kích hoạt ghi nhận ba lịch `launchd` đã được cài trên máy macOS ngày 29/10/2026. Trạng thái chạy hiện thời chưa được xác minh trên checkout Windows này.
- Nhánh `c` đã được tạo local. Working tree còn thay đổi chưa commit; chưa có xác nhận push hoặc pull request.
- Đề xuất phạm vi nghiệm thu cốt lõi là historical A/B/C. Nhóm cần xác nhận quyết định phạm vi trước khi chốt bàn giao.
- API collection và unified loader có mã nguồn trong checkout, nhưng `data/api/tennis.sqlite3`, `runs/api/CURRENT.json` và `runs/unified/CURRENT.json` không có. Snapshot 70 trận API chỉ có bằng chứng lịch sử ngày 29/10/2026; không được xem là runtime data hiện có.
- Telegram và ba lịch `launchd` có báo cáo về lần vận hành macOS ngày 29/10/2026; trạng thái hiện tại chưa được xác minh. API/unified runtime, Telegram và lịch tự động nên được xếp phần mở rộng/chưa nghiệm thu cho đến khi nhóm chốt phạm vi và cung cấp artifact tương ứng.

## Bảng phạm vi bàn giao đề xuất

| Thành phần | Hiện trạng trong checkout | Bằng chứng chạy | Đề xuất |
| --- | --- | --- | --- |
| Historical A/B/C | Source, 11 raw file, manifest, 14 bảng và notebook có trong workspace; raw bị Git ignore | Manifest historical; chạy offline ngày 08/11/2026: 27.574 dòng xử lý, 14 bảng; 163 test pass | Phạm vi cốt lõi đề xuất |
| API collection / unified snapshot | Source có; API SQLite và hai con trỏ `CURRENT.json` không có | Biên bản snapshot 70 trận ngày 29/10/2026 là bằng chứng lịch sử | Phần mở rộng; cần phục hồi artifact đúng snapshot để nghiệm thu |
| Telegram | Source và cấu hình có; không kiểm tra nội dung database trạng thái | Báo cáo gửi xác nhận tại lần kích hoạt ngày 29/10/2026 | Phần mở rộng; trạng thái hiện tại chưa xác minh |
| Lịch tự động | Script setup có; checkout hiện tại là Windows, không xác nhận LaunchAgent trên máy macOS | Báo cáo ghi ba job được nạp ngày 29/10/2026 | Phần mở rộng; cần kiểm tra trên máy macOS nếu được đưa vào phạm vi |

Raw historical đang có trong workspace nhưng bị `.gitignore` loại khỏi Git. README/provenance nêu CC BY-NC-SA 4.0 với ghi công, phi thương mại và chia sẻ tương tự; chỉ nhãn license chưa đủ để xác nhận quyền phân phối một bundle cụ thể. Phương án mặc định đề xuất là bàn giao manifest/checksum để người nhận lấy lại nguồn; chỉ tạo bundle sau khi xác minh quyền và điều kiện phân phối.

## Giới hạn diễn giải dữ liệu

Thời lượng mùa 2015 có độ phủ thấp; các giá trị 987 và 1.146 phút vẫn được giữ với cờ review. Tỷ lệ và so sánh nhóm dùng mẫu số riêng theo từng metric. Phân tích mô tả không chứng minh quan hệ nhân quả. Dữ liệu API 2026 hiện chỉ phủ một khoảng ngày trong tháng 10, không phải trọn mùa.
