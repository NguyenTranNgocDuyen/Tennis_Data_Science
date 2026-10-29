# Đối chiếu công việc A và B với tài liệu phân công

## Thành viên A

| Yêu cầu | Sản phẩm và bằng chứng |
| --- | --- |
| Khảo sát và chọn nguồn phù hợp | reports/data_inventory.md ghi lý do chọn, kho gốc và nguồn tải thực tế |
| Chốt thời gian, loại giải, loại trận và điều kiện sử dụng | config/project.json và mục phạm vi, giấy phép trong data_inventory.md |
| Pipeline thu thập và ghi nguồn phiên bản | src/data_collection/ và data/provenance/source_manifest.json với commit URL SHA256 |
| Schema, chuẩn hóa cơ bản và kiểm tra đầu vào | data/schemas/tennis_schema.json và src/data_validation/ |
| Phát hiện trùng, thiếu bắt buộc, giá trị không hợp lệ | validation_issues.csv, duplicates.csv, quarantine.csv; kiểm thử các trường hợp này |
| Mẫu nhỏ cùng cấu trúc | data/sample/tennis_sample.csv và sample_manifest.json; 125 dòng nguồn, thêm 2 bản sao chủ đích |
| Kiểm thử kiểm định | tests/test_validation.py, kiểm tra cấu trúc và ngữ nghĩa, phiên bản nguồn và cache hỏng |
| Tái tạo đầu vào | scripts/run_pipeline.py tải nguồn ghim commit; --offline xác minh cache |

## Thành viên B

| Yêu cầu | Sản phẩm và bằng chứng |
| --- | --- |
| Pipeline tiền xử lý dùng schema chung | src/preprocessing/; cùng hàm clean_matches cho mẫu và thật |
| Quy tắc thiếu, trùng, kiểu, ngoại lệ | reports/data_quality.md và log cleaning_actions.csv |
| Đặc trưng theo nguồn thật | Mùa nguồn, năm ngày giải, nhóm sân, nhóm rank, score_status, upset và tỷ lệ giao bóng |
| Thống kê mô tả và phân phối | numeric_summary, score_status, surface_summary và notebook B |
| So sánh nhóm | duration_by_surface_format, upsets_by_surface_format, rank_group_performance, serve_by_surface |
| Xu hướng thời gian | season_summary, season_surface, missingness_by_season |
| Bảng ổn định cho C | 14 CSV cùng table_contract.json; test hợp đồng mẫu và thật giống nhau |
| Kiểm tra đúng chỉ số | verify_tables và tests/test_analysis.py kiểm tra mẫu số upset, hai phía người chơi, tỷ lệ gộp |
| Notebook EDA | notebooks/member_b_eda.ipynb, 10 ô code chạy không lỗi và 5 hình |
| Báo cáo trước và sau xử lý | reports/data_quality.md, quality_by_field.csv và log từng hành động |
| Kết luận có số liệu và giới hạn | reports/eda_findings.md, có phân tích độ nhạy và thiếu dữ liệu theo mùa |
| Kiểm thử tiền xử lý | tests/test_preprocessing.py; bổ sung test_analysis.py và test_handoff.py |
| Tái tạo kết quả | scripts/verify_reproducibility.py so SHA256 lần chạy offline ở thư mục tạm |

## Phần giữ lại cho C

C nhận bảng đã xác minh để viết module biểu đồ, notebook C, insight trực quan và báo cáo cuối kỳ. Hình khám phá trong notebook B phục vụ EDA, không thay thế các đầu ra riêng của C. Chưa thực hiện đẩy GitHub, tạo PR hoặc xuất bản dự án.
