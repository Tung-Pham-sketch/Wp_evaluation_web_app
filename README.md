# VAECO Workpack Evaluation · Ver3

Ứng dụng web nội bộ hỗ trợ tiếp nhận Tally Sheet, đọc cấu trúc Excel, đối chiếu dữ liệu AMOS, review kết quả và xuất báo cáo đánh giá Workpack.

Phiên bản hiện tại được tổ chức theo package `wp_app` để có thể mở rộng parser theo khách hàng, logic matching, API và báo cáo mà không tiếp tục dồn mã vào một file duy nhất.

## 1. Chức năng chính

- Quản lý quy trình đánh giá Workpack theo 5 bước.
- Đọc Tally Sheet VietJet và Workpackage Summary Lufthansa.
- Nhập dữ liệu tham chiếu từ AMP VNA, Customer AMP và Jobcard master.
- Matching theo ba lớp: khóa chính xác, tiền tố mã và nội dung Title.
- Phân biệt `Đã khớp`, `Cần review`, `Không tìm thấy` và `Không áp dụng`.
- Review Detailed Task List, Important Jobs và Database to be Updated.
- Lưu lịch sử thay đổi thủ công.
- Xuất Excel bản nháp hoặc bản chính thức.

## 2. Công nghệ

- Python 3.11 trở lên.
- FastAPI và Uvicorn.
- SQLite.
- OpenPyXL.
- HTML, CSS và JavaScript thuần.
- `unittest` cho kiểm thử hồi quy.

## 3. Cấu trúc dự án

```text
wp_demo_app_ver3/
├── app.py                         # Điểm chạy tương thích: uvicorn app:app
├── wp_app/
│   ├── main.py                    # Khởi tạo FastAPI, startup và đăng ký router
│   ├── config.py                  # Đường dẫn, biến môi trường và giới hạn upload
│   ├── database.py                # Kết nối, schema và migration SQLite tối thiểu
│   ├── adapters.py                # Registry customer → parser/inspector
│   ├── parsers.py                 # Parser VietJet và Lufthansa
│   ├── matching.py                # Thuật toán matching độc lập với HTTP
│   ├── services.py                # Quy trình, đánh giá, migration và seed dữ liệu
│   ├── reference_data.py          # Nhập AMP, Customer AMP và Jobcard master
│   ├── utils.py                   # Chuẩn hóa chuỗi, cột và MHR
│   └── api/
│       ├── dashboard.py           # Dashboard và trình duyệt dữ liệu
│       ├── tallies.py             # Upload, inspect, evaluate và workflow
│       └── evaluations.py         # Review, report, history và export
├── templates/
│   └── index.html                 # HTML shell
├── static/
│   ├── app-ver3.js                # Giao diện và gọi API
│   ├── app.css                    # Style tổng thể
│   └── grid.css                   # Grid, workflow và Final Evaluation
├── tests/
│   ├── test_matching.py           # Matching và parser regression
│   └── test_app_structure.py      # Registry adapter và contract API
├── data/                           # Runtime; không đưa lên Git
├── requirements.txt
└── BAN_GIAO_CODEX.md              # Hồ sơ tiếp quản trên máy/Codex khác
```

Nguyên tắc phụ thuộc:

```text
API routes → services/reference_data → adapters/parsers/matching → database/config
```

`matching.py` và `parsers.py` không phụ thuộc giao diện web, nhờ đó có thể kiểm thử độc lập.

## 4. Dữ liệu đầu vào bên ngoài repository

Mặc định ứng dụng tìm dữ liệu ở thư mục cha của repository:

```text
DEMO DE TAI/
├── DATABASE/
│   ├── ALL AMP Task.xlsx
│   ├── ALL Customer AMP.xlsx
│   └── All Jobcard.xlsx
├── TALLY SHEET KHACH HANG/
│   ├── (Sample) TALLY SHEET WP VJC-A699-24MT2026 REV02.xlsx
│   └── (Sample) Workpackage-Summary for D-AIXB_H-25-29102025.xlsx
└── wp_demo_app_ver3/
```

Nếu thiếu các file nguồn:

- Ứng dụng vẫn khởi động.
- Kho AMOS/Jobcard có thể trống khi tạo database mới.
- Kiểm thử parser sample sẽ tự bỏ qua.
- Không thể seed hai hồ sơ mẫu.

Không commit file Excel nghiệp vụ hoặc database runtime nếu chưa được phép chia sẻ.

## 5. Cài đặt trên Windows

Mở PowerShell trong thư mục `wp_demo_app_ver3`:

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Chạy ứng dụng:

```powershell
python -m uvicorn app:app --reload --port 8001
```

Mở:

- Ứng dụng: `http://127.0.0.1:8001`
- OpenAPI: `http://127.0.0.1:8001/docs`

Không cần thay đổi lệnh chạy sau khi tái cấu trúc vì `app.py` vẫn xuất đối tượng `app`.

## 6. Cấu hình môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `WP_DATA_DIR` | `<repo>/data` | Thư mục chứa SQLite và uploads. |
| `WP_SKIP_SEED_SAMPLES` | Không đặt | Đặt bằng `1` để không tự tạo dữ liệu mẫu khi database trống. |

Ví dụ dùng thư mục dữ liệu riêng:

```powershell
$env:WP_DATA_DIR = 'D:\VAECO_DATA\wp_demo_ver3'
$env:WP_SKIP_SEED_SAMPLES = '1'
python -m uvicorn app:app --reload --port 8001
```

## 7. Quy trình nghiệp vụ 5 bước

1. Tiếp nhận file và metadata.
2. Đọc cấu trúc, kiểm tra sơ bộ và xác nhận dữ liệu.
3. Chạy matching với dữ liệu AMOS/Customer AMP.
4. Review kết quả, Important Jobs và task thiếu database.
5. Hoàn thiện Final Evaluation và xuất Excel.

Mỗi bước hoàn thành tương ứng 20% tiến độ. Báo cáo xuất khi quy trình chưa hoàn tất được đánh dấu `BẢN NHÁP` và có tiền tố `DRAFT_`.

## 8. Quy tắc matching hiện tại

### Phạm vi nguồn

- VietJet: chỉ `Block Taskcard` được coi là dòng MPD cần matching.
- Lufthansa: chỉ `MS Item` được matching; các block còn lại được nhận diện để review riêng.
- AMP VNA được ưu tiên trước Customer AMP.
- DLH A350 chỉ dùng Customer AMP có customer DLH và model A350.
- Model A320/A321 của AMP VNA được suy ra từ `AMP Name/Rev No.`.

### Ba lớp matching

1. Khớp chính xác theo Taskcard/Event Number và đúng customer/model.
2. Nếu không có kết quả, đề xuất candidate có tiền tố chung tối thiểu 4 ký tự và điểm từ 60%.
3. Nếu lớp 2 không đạt, đề xuất theo Title với điểm từ 65%.

Chỉ lớp 1 hợp lệ mới tự động đưa MHR vào kết quả. Lớp 2 và 3 luôn yêu cầu người dùng review.

## 9. Database runtime

Database mặc định: `data/wp_demo.db`.

Các bảng chính:

| Bảng | Nội dung |
|---|---|
| `amp_task` | AMP VNA và Customer AMP đã chuẩn hóa. |
| `jobcard_master` | Danh mục Jobcard. |
| `external_data` | Mapping và danh mục ngoài AMOS. |
| `tally_sheet` | Hồ sơ và file nguồn. |
| `workflow_step` | Trạng thái năm bước. |
| `evaluation` | Header lần đánh giá. |
| `evaluation_item` | Kết quả matching từng dòng. |
| `change_log` | Lịch sử chỉnh sửa thủ công. |

`init_db()` tạo schema mới và bổ sung các cột tương thích cho database cũ. Đây chưa phải hệ thống migration đầy đủ như Alembic; khi schema phát triển lớn hơn cần chuyển sang migration có version.

Để tạo database sạch:

```powershell
# Dừng ứng dụng trước. Sao lưu nếu cần giữ dữ liệu.
Remove-Item -LiteralPath .\data\wp_demo.db
python -m uvicorn app:app --port 8001
```

## 10. API chính

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| GET | `/api/dashboard` | Tổng quan và danh sách workflow. |
| GET | `/api/data/amos` | Tra cứu AMP. |
| GET | `/api/data/jobcards` | Tra cứu Jobcard. |
| GET | `/api/data/external` | Tra cứu dữ liệu ngoài AMOS. |
| POST | `/api/tallies` | Tạo hồ sơ từ file `.xlsx`. |
| POST | `/api/tallies/{id}/inspect` | Đọc và kiểm tra sơ bộ. |
| POST | `/api/tallies/{id}/inspection/confirm` | Xác nhận dữ liệu đầu vào. |
| POST | `/api/tallies/{id}/evaluate` | Chạy đánh giá sơ bộ. |
| GET | `/api/workflows/{id}` | Đọc trạng thái quy trình. |
| PATCH | `/api/workflows/{id}/review-checklist` | Cập nhật checklist review. |
| GET | `/api/evaluations/{id}` | Chi tiết và danh sách task. |
| PATCH | `/api/items/{item_id}` | Cập nhật một task review. |
| PATCH | `/api/evaluations/{id}` | Lưu Final Evaluation. |
| GET | `/api/evaluations/{id}/report/{kind}` | Important/database/scope report. |
| GET | `/api/evaluations/{id}/export` | Xuất Excel. |
| GET | `/api/evaluations/{id}/history` | Lịch sử thay đổi. |
| GET | `/api/tally/{id}/download` | Tải file nguồn. |

## 11. Kiểm thử

Chạy toàn bộ kiểm thử:

```powershell
python -m unittest discover -s tests -v
```

Kiểm tra cú pháp:

```powershell
python -m compileall -q app.py wp_app tests
node --check static\app-ver3.js
```

Khi sửa parser hoặc matching, bắt buộc bổ sung test hồi quy trước khi thay đổi dữ liệu mẫu hoặc ngưỡng điểm.

## 12. Mở rộng dự án

### Thêm customer/parser mới

1. Viết parser trong `wp_app/parsers.py` hoặc module parser riêng nếu lớn.
2. Parser phải trả về contract gồm tối thiểu `task_no`, `source_title`, `event_type` và các trường nguồn liên quan.
3. Đăng ký `AdapterDefinition` trong `wp_app/adapters.py`.
4. Thêm lựa chọn customer ở giao diện.
5. Viết test parser và test eligibility/matching.

### Thêm module API mới

1. Tạo router trong `wp_app/api/`.
2. Đặt logic nghiệp vụ trong service, không viết trực tiếp vào route nếu logic có thể tái sử dụng.
3. Đăng ký router tại `wp_app/main.py`.
4. Bổ sung contract test và cập nhật bảng API trong README.

### Thay đổi schema

1. Sao lưu database runtime.
2. Cập nhật schema và migration trong `wp_app/database.py`.
3. Đảm bảo migration chạy lặp lại không gây lỗi.
4. Kiểm thử cả database mới và database hiện hữu.
5. Tăng `MATCH_LOGIC_VERSION` nếu thay đổi làm kết quả matching cũ cần dựng lại.

## 13. Giới hạn hiện tại

- Chưa có đăng nhập, phân quyền hoặc audit bảo mật cấp production.
- SQLite phù hợp demo/nội bộ một tiến trình; chưa phù hợp nhiều người ghi đồng thời.
- Frontend vẫn là một file JavaScript lớn và nên tiếp tục chia module khi thêm nhiều màn hình.
- Check Scope chưa có nguồn Task–Check/Linked Check để tự động đánh giá.
- TAT hiện nhập thủ công.
- Chưa có pipeline CI/CD và migration framework độc lập.

## 14. Checklist trước khi push

```powershell
git status --short
python -m unittest discover -s tests -v
python -m compileall -q app.py wp_app tests
node --check static\app-ver3.js
git diff --check
```

Kiểm tra thêm:

- Không có database, file upload, `.env` hoặc dữ liệu khách hàng trong commit.
- README và `BAN_GIAO_CODEX.md` đã phản ánh đúng thay đổi.
- Không ghi đè các thay đổi chưa commit của người khác.

## 15. Bàn giao sang máy khác

Đọc [BAN_GIAO_CODEX.md](BAN_GIAO_CODEX.md) để tiếp tục trên Codex hoặc máy công ty. Git chỉ mang theo source code; nếu cần giữ đúng dữ liệu demo hiện tại, phải sao chép riêng `data/wp_demo.db` và `data/uploads/` qua kênh nội bộ được phép.

