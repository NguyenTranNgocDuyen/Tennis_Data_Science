# Đồ án khoa học dữ liệu tennis

**Tài liệu bàn giao trực quan hoá:** [nguồn dữ liệu, flow pipeline, ngoại lệ/alert và biểu đồ ưu tiên](docs/data_pipeline_visualization.md) · [sơ đồ SVG](docs/figures/pipeline_flow.svg).

**Bộ dữ liệu chung mới:** [schema chung và incremental load hằng tuần](docs/unified_schema.md). GitHub và API đã được chuẩn hóa định danh, vòng đấu và ý nghĩa trường; bản khởi tạo có 27.644 trận, 14 bảng phân tích. B/C đọc `runs/unified/CURRENT.json`. Job thứ Hai 07:40 thực hiện đối soát API và nạp bộ chung theo chuỗi tuần tự; lịch raw hằng ngày giữ nguyên.

Dự án triển khai thu thập, kiểm định, làm sạch, tạo đặc trưng và phân tích thống kê theo tài liệu phân công. Dữ liệu thật là đơn nam cấp tour mùa 2015–2025, do Jeff Sackmann / Tennis Abstract biên soạn; sử dụng bản lưu trữ ghim phiên bản vì kho gốc trả về 404 khi triển khai. Đã kèm dữ liệu gốc, dữ liệu xử lý, báo cáo và notebook chạy có kết quả.

Đã bổ sung **luồng API cập nhật định kỳ**: [hướng dẫn cấu hình RapidAPI và lịch chạy](docs/api_batch.md). Luồng này lưu SQLite, có quota, phân trang, cập nhật không trùng và xuất dữ liệu bằng B. Đã chạy API thật và kích hoạt lịch tự động ngày 29 tháng 10 năm 2026; dữ liệu và kết quả nghiệm thu ở [báo cáo kích hoạt](reports/live_activation.md). Credential đọc từ .env trên máy, không chia sẻ trong gói bàn giao.

[Nghiệm thu phần API](reports/api_acceptance.md) ghi kết quả 80 kiểm thử, chạy lại demo và trạng thái lịch chạy. [Nghiệm thu A B ban đầu](reports/acceptance.md) là bằng chứng của phiên bản dữ liệu lịch sử ngày 28 tháng 10.

Đã bổ sung [phục hồi từ raw, log và cảnh báo Telegram](docs/recovery_and_alerts.md). Có replay offline không cần SQLite gốc, resume chỉ lấy phần còn thiếu, log theo operation và outbox Telegram phân loại P1–P4, gộp lỗi trùng 30 phút. Hiện gửi tin riêng từ bot tới cá nhân bạn; điền token/ID chat cá nhân trong .env. Demo/replay không gửi tin thật. Xem [nghiệm thu phục hồi và cảnh báo](reports/recovery_alert_acceptance.md) cho kiểm chứng phiên bản ban đầu.

```bash
# Thử luồng API không cần key, lưu riêng runs/api_demo
.venv/bin/python scripts/run_api_batch.py --demo

# Sau khi điền RAPIDAPI_KEY trong .env
.venv/bin/python scripts/run_api_batch.py
```

## Bắt đầu với sản phẩm đã có

- [Báo cáo kiểm kê của A](reports/data_inventory.md): nguồn, phạm vi, giấy phép và từ điển đủ 52 cột.
- [Báo cáo chất lượng của B](reports/data_quality.md): quy tắc xử lý và bằng chứng từng loại lỗi.
- [Phân tích và kết luận của B](reports/eda_findings.md): số liệu, mẫu số, độ nhạy và hạn chế.
- [Notebook EDA đã chạy](notebooks/member_b_eda.ipynb): tái tính, đối chiếu bảng và các hình khám phá.
- [Hợp đồng bàn giao cho C](docs/data_contract.md): giao diện hàm, ý nghĩa đặc trưng và 14 bảng kết quả.
- [Bằng chứng nghiệm thu](reports/acceptance.md): các kiểm thử và kiểm tra tái lập đã thực hiện.
- [Kế hoạch C](docs/visualization_plan.md), [notebook C](notebooks/member_c_visualization.ipynb), [insight C](reports/insights.md), [báo cáo tổng hợp](reports/final_report.md) và [nghiệm thu Windows](reports/final_acceptance.md).

Phần C dùng các bảng historical tại `reports/tables/`, không gộp với API/unified snapshot. Chạy `python scripts/export_visualizations.py` để xuất PNG/SVG vào `reports/figures/`. Không cần token hay API trả phí cho A/B/C historical.

## Cài đặt và chạy lại

Đã kiểm tra trên macOS ARM64, Python 3.13.7; phiên bản Python thực tế của lần chạy được ghi trong run_manifest.json. Chạy từ thư mục dự án. requirements.txt ghim các thư viện trực tiếp; requirements-lock.txt chụp toàn bộ môi trường thực thi.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Dữ liệu raw đã có: xác minh checksum và chạy hoàn toàn offline
.venv/bin/python scripts/run_pipeline.py --offline

# Máy mới chưa có raw: tải snapshot ghim commit, rồi xử lý
.venv/bin/python scripts/run_pipeline.py

# Dữ liệu mẫu chạy cùng pipeline, đầu ra riêng ở runs/sample
.venv/bin/python scripts/run_pipeline.py --sample

# Kiểm thử các quy tắc và chỉ số
.venv/bin/python -m pytest -q

# Tái chạy vào thư mục tạm, đối chiếu byte toàn bộ đầu ra
.venv/bin/python scripts/verify_reproducibility.py
```

Tùy chọn `--output-dir /path/to/output` ghi kết quả vào thư mục khác để đối chiếu tái lập. Nếu cache raw bị sửa, pipeline dừng vì SHA256 không khớp; khôi phục đúng file nguồn từ URL trong manifest. Không sửa manifest để hợp thức hóa file đã bị thay đổi. Muốn thay snapshot hoặc mùa, tạo bản dự án riêng để giữ phiên bản này tái lập được.

## Chạy notebook

```bash
.venv/bin/python -m ipykernel install --prefix .venv --name tennis-khdl --display-name 'Python (Tennis A B)'
.venv/bin/python scripts/execute_notebook.py
```

Mở notebook bằng VS Code/Jupyter và chọn kernel tương ứng nếu muốn tương tác. JupyterLab không phải phụ thuộc bắt buộc để thực thi tự động. Script build_notebook.py chỉ để tái tạo nội dung notebook, sẽ xóa output cũ; sau đó phải chạy execute_notebook.py lại. Notebook đã giao giữ output để người nhận kiểm tra; khi tạo PR có thể xóa output hình lớn nếu nhóm thống nhất.

## Cấu trúc

```text
config/project.json                 Phạm vi, commit nguồn, quy tắc loại giải
src/data_collection/                A thu thập và cache có checksum
src/data_validation/                A schema và kiểm định ngữ nghĩa
src/preprocessing/                  B làm sạch, cách ly và tạo đặc trưng
src/analysis/                       B thống kê, đối soát và sinh báo cáo
data/schemas/tennis_schema.json      Hợp đồng CSV 1.0.0
data/sample/tennis_sample.csv        Dòng thật, trường thiếu và hai bản sao chủ đích
data/provenance/                    Manifest, README và giấy phép nguồn
data/raw/                          CSV gốc bất biến
data/interim/                      Vi phạm, hành động sửa, dòng loại và cách ly
data/processed/                    Bảng trận và lượt người chơi
reports/tables/                    Bảng CSV có hợp đồng cho C
notebooks/member_b_eda.ipynb         Notebook B đã thực thi
scripts/run_pipeline.py             Điểm chạy toàn pipeline
tests/                             Kiểm thử schema, làm sạch, thống kê và cache
```

## Quyết định phân tích cần giữ khi bàn giao

- `tourney_date` là ngày bắt đầu/tuần giải; `season` lấy từ file nguồn, không mặc định bằng năm của ngày giải. `match_num` không phải thứ tự thời gian.
- Giữ A M G F; loại giải đồng đội, Olympic và Next Gen bằng tên không phân biệt hoa thường. Chi tiết trong config và báo cáo kiểm kê.
- Trận RET/W/O/DEF được giữ trong kiểm kê; chỉ completed đi vào so sánh thi đấu. Tỷ lệ upset loại rank thiếu hoặc bằng nhau.
- Không điền rank, minutes hoặc stats thiếu bằng 0/trung bình. Lỗi tùy chọn được đặt thiếu và ghi log; khóa mâu thuẫn bị cách ly toàn bộ.
- Thời lượng đáng ngờ được gắn cờ; median và bảng độ nhạy hỗ trợ diễn giải. Nguồn có thời lượng 987 và 1.146 phút ở trận 3 set chưa được đối chiếu độc lập. Năm 2015 có độ phủ thời lượng thấp nên thận trọng với xu hướng.
- Tỷ lệ giao bóng dùng tổng tử số / tổng mẫu số trên cùng cặp có dữ liệu. Thống kê nhóm rank tính cả thắng và thua. Mỗi bảng nêu rõ mẫu số.

## Nguồn và giấy phép

Dữ liệu do **Jeff Sackmann / Tennis Abstract** biên soạn. [Kho gốc](https://github.com/JeffSackmann/tennis_atp), [bản lưu trữ](https://github.com/Aneeshers/tennis-sackmann-archive/tree/83733587353df8a41f2fd4f516147d5aa83f5a8d), commit `83733587353df8a41f2fd4f516147d5aa83f5a8d`, truy cập 2026-10-28. Dữ liệu và dữ liệu phái sinh được sử dụng/chia sẻ theo [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): ghi công, phi thương mại, chia sẻ cùng điều kiện; đã lọc và làm sạch như báo cáo mô tả. Không tuyên bố đây là dữ liệu chính thức đã xác minh bởi ATP.

`.gitignore` bỏ qua raw/interim/processed và môi trường ảo để không commit dữ liệu lớn; mẫu và manifest được giữ. Trạng thái push/PR phải được xác minh trên GitHub; có remote `origin` không đủ để kết luận. Tài liệu `launchd` là bằng chứng macOS lịch sử, không khẳng định scheduler đang chạy trên Windows.
