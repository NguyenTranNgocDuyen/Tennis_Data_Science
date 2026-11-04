# Đối chiếu đầu ra với tài liệu phân công

Tài liệu phân công nêu đầu ra bắt buộc của A/B/C và một số khuyến nghị quy trình GitHub. Bảng dưới ghi nhận những gì đang có trong working tree; trạng thái test được dẫn từ báo cáo nghiệm thu, không mặc định là đã chạy lại mỗi lần mở repo.

## Thành viên A — dữ liệu

| Yêu cầu | Bằng chứng trong repo | Trạng thái |
| --- | --- | --- |
| Chọn nguồn, phạm vi, giấy phép và hạn chế | `reports/data_inventory.md`, `config/project.json`, `data/provenance/` | Có |
| Thu thập và truy xuất phiên bản nguồn | `src/data_collection/`, `data/provenance/source_manifest.json` | Có |
| Schema và kiểm định đầu vào | `data/schemas/tennis_schema.json`, `src/data_validation/`, `tests/test_validation.py` | Có |
| Phát hiện lỗi, trùng, quarantine | Pipeline ghi `data/interim/`; quy tắc và số liệu ở `reports/data_quality.md` | Có |
| Dữ liệu mẫu chung | `data/sample/tennis_sample.csv`, `data/sample/sample_manifest.json` | Có; 125 dòng gốc và 2 bản sao có chủ đích |
| Tái tạo dữ liệu | `scripts/run_pipeline.py --offline`; 11 file raw hiện có và checksum được xác minh trong lần chạy 02/11/2026 | Có, đã xác minh |

## Thành viên B — tiền xử lý và phân tích

| Yêu cầu | Bằng chứng trong repo | Trạng thái |
| --- | --- | --- |
| Làm sạch, xử lý thiếu/trùng/kiểu/ngoại lệ | `src/preprocessing/`, `reports/data_quality.md` | Có |
| Đặc trưng và thống kê mô tả/so sánh/xu hướng | `src/analysis/`, `reports/tables/` | Có; 14 bảng theo hợp đồng |
| Kiểm tra chỉ số và giao diện bàn giao | `tests/test_analysis.py`, `tests/test_handoff.py`, `reports/tables/table_contract.json`, `docs/data_contract.md` | Có |
| Notebook và diễn giải có giới hạn | `notebooks/member_b_eda.ipynb`, `reports/eda_findings.md` | Có |
| Kiểm thử | `tests/test_preprocessing.py`, `tests/test_analysis.py` và các test liên quan | Có; nghiệm thu 01/11 ghi 158 pass, chưa chạy lại trong lần rà soát 02/11 |

## Thành viên C — trực quan hóa và báo cáo

| Yêu cầu | Bằng chứng trong repo | Trạng thái |
| --- | --- | --- |
| Hàm biểu đồ có hợp đồng và export | `src/visualization/`, `tests/test_visualization.py` | Có |
| Notebook, hình đầu ra, insight | `notebooks/member_c_visualization.ipynb`, `reports/figures/`, `reports/insights.md` | Có; 6 biểu đồ PNG và SVG |
| Báo cáo tổng hợp | `reports/final_report.md` | Có |
| Nghiệm thu Windows | `reports/final_acceptance.md` | Có; cập nhật trạng thái xác minh mới nhất trong báo cáo này |

## Tái lập và quy trình bàn giao

- Lần chạy offline ngày 02/11/2026 xử lý 30.616 dòng nguồn, giữ 27.574 dòng, sinh 14 bảng và không còn lỗi kiểm định sau xử lý. So sánh SHA-256 với manifest: 11/11 file nguồn, 41/41 file mã/schema và 26/26 artifact khớp.
- `scripts/verify_reproducibility.py` không chạy trọn trong sandbox Windows vì quyền tạo thư mục tạm bị từ chối. Kết quả trên được xác minh bằng cách chạy pipeline offline vào một output directory đã tạo sẵn trong workspace và so manifest.
- Nhánh local hiện tại là `c`. Thay đổi chưa commit vẫn còn trong working tree. Tài liệu phân công khuyến nghị branch/PR và review; chưa có bằng chứng PR/push trong lần rà soát này, nên không đánh dấu quy trình GitHub là hoàn tất.
- Luồng API, unified load và Telegram là phần mở rộng. Trạng thái lịch `launchd` được ghi nhận là đã cài trên máy macOS ngày 29/10/2026; hoạt động hiện thời không được xác minh trên Windows.
