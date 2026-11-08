# Đồ án khoa học dữ liệu tennis

**Tài liệu bàn giao trực quan hoá:** [nguồn dữ liệu, flow pipeline, ngoại lệ/alert và biểu đồ ưu tiên](docs/data_pipeline_visualization.md) · [sơ đồ SVG](docs/figures/pipeline_flow.svg).

**Bộ dữ liệu chung:** [schema và hướng dẫn tạo snapshot](docs/unified_schema.md). Biên bản nghiệm thu ngày 29/10/2026 ghi nhận snapshot ban đầu có 27.644 trận (27.574 GitHub và 70 API), cùng 14 bảng. Snapshot ở `runs/unified/` là đầu ra runtime và không được commit; tệp `runs/unified/CURRENT.json` không có trong checkout sạch. Không coi số liệu 70 API trong biên bản là dữ liệu có sẵn ở checkout này.

Muốn tạo snapshot chung, dùng macOS/Linux/WSL2, cài dependencies, có dữ liệu raw lịch sử và kết nối GitHub để khởi tạo tham chiếu người chơi. Từ thư mục gốc, chạy `python scripts/run_unified_load.py --refresh-reference`. Nếu chưa có `data/api/tennis.sqlite3`, snapshot chỉ gồm phần lịch sử; lệnh này không tự khôi phục 70 trận API. Lưu ý `--refresh-reference` cũng có thể gọi Tennis API: khi database API đã có trận cần bổ sung metadata nhánh đấu, metadata chưa có trong cache và có `RAPIDAPI_KEY` trong `.env`, quá trình tra cứu có thể gửi request mới và tiêu thụ quota. Database rỗng/không có trận cần tra cứu, metadata đã được cache hoặc thiếu key sẽ không tạo request mạng mới cho việc làm giàu này. Muốn đối soát và nạp dữ liệu API mới, cần cấu hình credential cục bộ và chủ động chạy `python scripts/run_unified_load.py --collect --refresh-reference`; `--collect` gọi luồng đối soát API, còn `--refresh-reference` có thể phát sinh request riêng như điều kiện trên. Chi tiết điều kiện và phục hồi ở [docs/unified_schema.md](docs/unified_schema.md). Script unified hiện dùng `fcntl`, nên không chạy trực tiếp bằng Python Windows native.

Dự án triển khai thu thập, kiểm định, làm sạch, tạo đặc trưng và phân tích thống kê theo tài liệu phân công. Dữ liệu thật là đơn nam cấp tour mùa 2015–2025, do Jeff Sackmann / Tennis Abstract biên soạn; sử dụng bản lưu trữ ghim phiên bản vì kho gốc trả về 404 khi triển khai. Repository gồm mã nguồn, schema, dữ liệu mẫu, báo cáo và notebook. Các thư mục dữ liệu đầy đủ `data/raw/`, `data/interim/` và `data/processed/` bị `.gitignore` bỏ qua; khi checkout mới, tải hoặc tạo lại theo hướng dẫn trong phần Cài đặt và chạy lại.

Đã bổ sung **luồng API cập nhật định kỳ**: [hướng dẫn cấu hình RapidAPI và lịch chạy](docs/api_batch.md). Luồng này lưu SQLite, có quota, phân trang, cập nhật không trùng và xuất dữ liệu bằng B. Báo cáo ghi nhận đã chạy API thật và cài lịch `launchd` trên máy macOS ngày 29 tháng 10 năm 2026; trạng thái lịch hiện thời chưa được xác minh trên checkout Windows này. Xem [báo cáo kích hoạt](reports/live_activation.md). Credential đọc từ `.env` cục bộ, không chia sẻ trong gói bàn giao.

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

# Mỗi lần chạy cần output directory mới hoặc đang trống; pipeline không ghi artifact vào thư mục gốc

# Dữ liệu raw đã có: xác minh checksum và chạy hoàn toàn offline
.venv/bin/python scripts/run_pipeline.py --offline --output-dir ../tennis-output-offline

# Máy mới chưa có raw: tải snapshot ghim commit, rồi xử lý
.venv/bin/python scripts/run_pipeline.py --output-dir ../tennis-output-download

# Chạy pipeline trên bộ dữ liệu mẫu vào output directory riêng
.venv/bin/python scripts/run_pipeline.py --sample --output-dir ../tennis-output-sample

# Chỉ tạo lại bộ dữ liệu mẫu khi cần; file được ghi trong output directory đã chọn
.venv/bin/python scripts/run_pipeline.py --offline --generate-sample --output-dir ../tennis-output-with-sample

# Kiểm thử các quy tắc và chỉ số
.venv/bin/python -m pytest -q

# Tái chạy vào thư mục tạm, đối chiếu byte toàn bộ đầu ra
.venv/bin/python scripts/verify_reproducibility.py
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Dùng dữ liệu raw đã có, chạy hoàn toàn offline
.\.venv\Scripts\python.exe scripts\run_pipeline.py --offline --output-dir ..\tennis-output-offline

# Chạy pipeline trên bộ dữ liệu mẫu vào output directory riêng
.\.venv\Scripts\python.exe scripts\run_pipeline.py --sample --output-dir ..\tennis-output-sample

# Tạo sample riêng trong output directory khi được yêu cầu
.\.venv\Scripts\python.exe scripts\run_pipeline.py --offline --generate-sample --output-dir ..\tennis-output-with-sample

# Chạy test; basetemp trong project tránh một số cấu hình Windows chặn %TEMP%
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp -p no:cacheprovider

# Xác minh tái lập
.\.venv\Scripts\python.exe scripts\verify_reproducibility.py
```

`--output-dir /path/to/output` là bắt buộc và phải chỉ tới thư mục mới hoặc đang trống; pipeline dừng nếu thư mục đích đã có nội dung hoặc trỏ tới thư mục gốc repository. Nếu cache raw bị sửa, pipeline dừng vì SHA256 không khớp; khôi phục đúng file nguồn từ URL trong manifest. Không sửa manifest để hợp thức hóa file đã bị thay đổi. Muốn thay snapshot hoặc mùa, tạo bản dự án riêng để giữ phiên bản này tái lập được.

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
