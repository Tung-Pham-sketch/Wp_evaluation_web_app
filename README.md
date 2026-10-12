# VAECO Workpack Evaluation · Ver3 (bản hợp nhất)

Ứng dụng web nội bộ hỗ trợ tiếp nhận Tally Sheet, đọc cấu trúc Excel, đối chiếu dữ liệu AMOS, review kết quả và xuất báo cáo đánh giá Workpack.

Bản này hợp nhất hai nhánh:

- **Nhánh Ver3 (package `wp_app`)**: cấu trúc package, quy trình 5 bước, bộ đọc khối Lufthansa, Jobcard master, xuất Excel bản nháp, kiểm thử, giao diện/CSS.
- **Nhánh MPD key**: luồng matching theo MPD key (lớp 1), cột AMOS Reference / Match Note, popup đối chiếu AMOS, xuống dòng trong lưới, "Thêm vào Database" / "Sửa bản ghi" trên MiniDB, xuất danh sách thay đổi MiniDB, xóa hồ sơ, form tiếp nhận bắt buộc đủ trường.

Lớp 2–3 của Ver3 (tiền tố mã, Title) được giữ lại, chỉ chạy khi lớp 1 không tìm thấy, là gợi ý cần review và không gán MHR.

## 1. Chức năng chính

- Quy trình đánh giá Workpack 5 bước, tiến độ 20%/bước.
- Đọc Tally Sheet VietJet và Workpackage Summary Lufthansa (nhận diện toàn bộ khối).
- Nhập AMP VNA (ALL AMP Task), Customer AMP và Jobcard master vào MiniDB.
- Matching:
  - Lớp 1 – MPD key, thứ tự nguồn theo cấu hình khách hàng, chia item theo LH/RH và ITEM.
  - Lớp 2 – tiền tố mã (≥ 4 ký tự, ≥ 60%), lớp 3 – Title (≥ 65%): chỉ là gợi ý.
- Trạng thái lưu trong DB: `AUTO_MATCH`, `REVIEW_REQUIRED`, `NOT_FOUND`, `NOT_APPLICABLE`; hiển thị: **Đã khớp / Cần review / Chưa khớp / Không áp dụng**.
- Popup đối chiếu Tally ↔ AMOS (Task No., Title, Zone, MHR), bản ghi đã chọn và các ứng viên khác ("Cùng AMP").
- Review Detailed Task List, Important Jobs, Database to be Updated; lịch sử thay đổi.
- Thêm task thiếu vào MiniDB, sửa bản ghi MiniDB (khóa trường nhận diện), xuất Excel danh sách thay đổi. **Chỉ MiniDB thay đổi, không bao giờ ghi vào AMOS.**
- Xuất Excel bản nháp (`DRAFT_`) hoặc chính thức.
- Xóa hồ sơ (giữ lại các thay đổi đã ghi vào MiniDB).

## 2. Công nghệ

Python 3.11+, FastAPI, Uvicorn, SQLite, OpenPyXL, HTML/CSS/JavaScript thuần, `unittest`.

## 3. Cấu trúc dự án

```text
wp_demo_app_ver3/
├── app.py                         # Điểm chạy tương thích: uvicorn app:app
├── wp_app/
│   ├── main.py                    # Khởi tạo FastAPI, startup và đăng ký router
│   ├── config.py                  # Đường dẫn, biến môi trường, MATCH_LOGIC_VERSION
│   ├── database.py                # Schema SQLite + migration (MERGED_MIGRATIONS)
│   ├── adapters.py                # Registry mẫu Tally → parser/inspector
│   ├── parsers.py                 # Parser VietJet và Lufthansa
│   ├── matching_config.py         # ★ Bảng cấu hình matching (alias khách hàng, customer-first)
│   ├── matching.py                # Hàm matching chung, lớp 2–3 (tiền tố, Title)
│   ├── mpd_matching.py            # ★ Lớp 1 – MPD key, chia item LH/RH, gộp item
│   ├── minidb.py                  # ★ Popup AMOS, Thêm/Sửa bản ghi MiniDB, xuất thay đổi
│   ├── services.py                # Quy trình 5 bước, đánh giá, migration, xóa hồ sơ
│   ├── reference_data.py          # Nhập AMP, Customer AMP, Jobcard master
│   ├── utils.py                   # Chuẩn hóa chuỗi, cột và MHR
│   └── api/
│       ├── dashboard.py           # Dashboard và Kho dữ liệu (lọc nguồn gốc)
│       ├── tallies.py             # Tiếp nhận, inspect, evaluate, workflow, xóa
│       ├── evaluations.py         # Review, report, history, export
│       └── records.py             # ★ Upload options, matching plan, popup, MiniDB records
├── templates/index.html
├── static/
│   ├── app-ver3.js                # Giao diện và gọi API
│   ├── app.css                    # Style tổng thể (+ khối "Merged features" ở cuối)
│   └── grid.css                   # Grid, workflow, Final Evaluation (+ wrap text ở cuối)
├── tests/
│   ├── test_app_structure.py      # Registry adapter và contract API
│   ├── test_matching.py           # Hàm matching, lookup lớp 1–3, parser regression
│   └── test_mpd_matching.py       # ★ Luồng MPD key, trạng thái, MiniDB
├── data/                          # Runtime; không đưa lên Git
├── requirements.txt
├── .gitignore
└── BAN_GIAO_CODEX.md
```

★ = file mới của bản hợp nhất. Nguyên tắc phụ thuộc giữ nguyên:

```text
API routes → services / minidb / reference_data → adapters / parsers / matching / mpd_matching → database / config
```

## 4. Dữ liệu đầu vào bên ngoài repository

```text
DEMO DE TAI/
├── DATABASE/
│   ├── ALL AMP Task.xlsx          # sheet "AMP" (nếu không có, dùng sheet đang mở)
│   ├── ALL Customer AMP.xlsx
│   └── All Jobcard.xlsx
├── TALLY SHEET KHACH HANG/
│   ├── (Sample) TALLY SHEET WP VJC-A699-24MT2026 REV02.xlsx
│   └── (Sample) Workpackage-Summary for D-AIXB_H-25-29102025.xlsx
└── wp_demo_app_ver3/
```

Cột ALL AMP Task được đọc: AMP Name/Rev No., AMP Date, MP Name/Issue No./Rev No., Taskcard No./Rev, Taskcard Ident., Type, Task No./Rev No., A/C Type, Effectivity, Taskcard Title, Description, Phase, Zone, Area, Panel, Special Code, Resource Type, Classification, Type Code, Qualification, Planning MHR, Information Skill, Information MHR, Requirement Link (hoặc References), Linked Jobcards, Jobcards Title. Customer AMP thêm Customer và Jobcard No.

Không commit file Excel nghiệp vụ hoặc database runtime (`.gitignore` đã loại trừ).

## 5. Cài đặt và chạy (Windows)

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8001
```

Mở `http://127.0.0.1:8001` (OpenAPI: `/docs`).

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `WP_DATA_DIR` | `<repo>/data` | Thư mục chứa SQLite và uploads. |
| `WP_SKIP_SEED_SAMPLES` | Không đặt | `1` để không tự tạo hồ sơ mẫu khi database trống. |

## 6. Quy trình nghiệp vụ 5 bước

1. **Tiếp nhận** – form bắt buộc: file, Khách hàng, Loại tàu bay (danh sách lấy từ MiniDB), Số đăng ký, Check Type, Mẫu Tally Sheet (đề xuất theo khách hàng, có thể đổi); Mô tả không bắt buộc. Form hiển thị thứ tự nguồn sẽ tìm.
2. **Đọc sơ bộ** và xác nhận dữ liệu đầu vào (Lufthansa: bảng khối đầy đủ).
3. **Đánh giá** – chạy matching (mục 7).
4. **Review** – checklist 3 nhóm; popup AMOS; Thêm vào Database / Sửa bản ghi.
5. **Hoàn thiện** – Final Evaluation (thông tin chung, tổng hợp giờ công, thống kê, giả định) và xuất Excel.

## 7. Quy tắc matching

### 7.1 Dòng nào được matching

| Mẫu | Dòng được matching | Mã dùng để matching |
|---|---|---|
| VietJet | `Block Taskcard`, và mọi Event có Title dạng `TASKNO (REV) / TITLE` | Mã trong Title nếu có, nếu không là Work Step / Event Number |
| Lufthansa | Mọi dòng có CRI (MS ITEMS và các khối khác có CRI) | CRI |

VietJet Event không có mã task trong Title (ví dụ dòng Check) → `NOT_APPLICABLE`, không bị đưa vào "Database to be Updated".

### 7.2 Lớp 1 – MPD key

MPD key = phần số của nhà sản xuất, bỏ hậu tố của nhà khai thác (`-1`, `-VJC`, `-ENG1`, `/rev`):

| Mẫu | Ví dụ → MPD key |
|---|---|
| A350 zonal `ZL-ddd-xxxxx-dd` | `ZL-455-00Z01-01-ENG1` → `ZL-455-00Z01-01` |
| A350 `dddddd-xxxxx-dd` | `271400-00M10-01-1` → `271400-00M10-01` |
| A320 family `dddddd-xx` | `361100-01-1-VJC` → `361100-01` |

Không đúng mẫu nào → dùng cả số (bỏ `/rev`).

Thứ tự nguồn (`mpd_matching.matching_plan`):

1. *(Nếu cấu hình)* Customer AMP của khách hàng – theo MPD key (mặc định: DLH + A350).
2. ALL AMP Task – theo MPD key, cùng họ tàu; ưu tiên AMP Name bắt đầu `HVN`, sau đó AMP Date mới nhất; lấy mọi item của AMP được chọn.
3. Customer AMP của khách hàng – số Jobcard khớp chính xác.
4. Customer AMP của khách hàng khác – số Jobcard khớp chính xác (luôn cuối cùng).

Các dòng Tally cùng MPD key được chia item: N:N theo LH/RH (ENG #1 → LH, ENG #2 → RH) rồi theo số ITEM; 1 dòng – nhiều item: cộng MHR; nhiều dòng – 1 item: dùng chung.

Trạng thái lớp 1:

- `AUTO_MATCH` – khớp, không có ghi chú cần kiểm tra. Ghi chú "Mã task lấy từ Title" chỉ là thông tin.
- `REVIEW_REQUIRED` (lớp 1, vẫn điền MHR) – nhiều dòng dùng chung 1 item, số dòng ≠ số item, không xác định LH/RH, hoặc lấy từ Customer AMP của khách hàng khác.

### 7.3 Lớp 2–3 – gợi ý

Chỉ chạy khi lớp 1 không tìm thấy (`services.lookup_amp(..., include_exact=False)`): lớp 2 tiền tố mã ≥ 4 ký tự và ≥ 60%, lớp 3 Title ≥ 65%. Kết quả `REVIEW_REQUIRED`, `matched = 0`, **không gán MHR**, chỉ điền `suggested_*`. Không tìm thấy → `NOT_FOUND` và đưa vào "Database to be Updated".

### 7.4 Cấu hình (không cần sửa code)

`wp_app/matching_config.py`:

```python
CUSTOMER_ALIASES = {"VA-VJ": {"VA-VJ", "VJC", "VIETJET", "VIETJET AIR"},
                    "DLH": {"DLH", "LUFTHANSA", "LUFTHANSA GERMAN AIRLINES"}}
CUSTOMER_FIRST = {"DLH": {"350"}}      # thêm: "VA-VJ": {"32S"},
DEFAULT_TALLY_FORMAT = "VietJet"
```

Mẫu Tally Sheet mới: đăng ký `AdapterDefinition` trong `wp_app/adapters.py`; nó tự xuất hiện trong form tiếp nhận.

## 8. MiniDB

- **Thêm vào Database** (dòng chưa khớp): chọn ALL AMP Task hoặc Customer AMP. Bắt buộc – VNA: Task No., A/C Type, AMP Name, AMP Date, Title; Customer: Task No., A/C Type, Customer, Title. Sau khi thêm, các dòng chưa khớp cùng MPD key trong hồ sơ được matching lại.
- **Sửa bản ghi** (từ popup AMOS hoặc Kho dữ liệu): trường nhận diện (source, AMP Name, Taskcard No., Ident., Task No., Customer, Effectivity, A/C Type) bị khóa.
- Mọi thay đổi ghi vào `amp_change`, xuất Excel tại Kho dữ liệu → "Xuất thay đổi MiniDB". Nếu MiniDB được dựng lại từ file AMOS mới, bản ghi thêm thủ công được giữ và các lần sửa được áp dụng lại.

## 9. Database runtime

| Bảng | Nội dung |
|---|---|
| `amp_task` | AMP VNA và Customer AMP (cột `origin` AMOS/MANUAL, `edited`, `mpd_key`, `side`…). |
| `jobcard_master` | Danh mục Jobcard. |
| `external_data` | Mapping và danh mục ngoài AMOS. |
| `tally_sheet` | Hồ sơ và file nguồn. |
| `workflow_step` | Trạng thái năm bước. |
| `evaluation` / `evaluation_item` | Header và kết quả từng dòng (`amos_reference`, `amp_refs`, `match_rule`, `added_to_db`…). |
| `change_log` | Lịch sử review thủ công. |
| `amp_change` | Lịch sử Thêm/Sửa bản ghi MiniDB. |

`MATCH_LOGIC_VERSION = 5`. Khi khởi động, hồ sơ được đánh giá bằng phiên bản cũ và **chưa có thao tác thủ công** (`change_log`, `amp_change`) sẽ được matching lại; hồ sơ có thao tác thủ công giữ nguyên kết quả, chỉ đổi nhãn trạng thái cũ ("Đã khớp"/"Chưa khớp") sang mã mới.

## 10. API

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| GET | `/api/dashboard` | Tổng quan và danh sách workflow. |
| GET | `/api/data/amos` | Tra cứu AMP (`origin` = all/amos/manual/edited). |
| GET | `/api/data/jobcards` | Tra cứu Jobcard. |
| GET | `/api/data/external` | Tra cứu dữ liệu ngoài AMOS. |
| GET | `/api/upload-options` | Danh sách khách hàng, loại tàu bay, mẫu Tally. |
| GET | `/api/matching-plan` | Thứ tự nguồn cho khách hàng/loại tàu bay. |
| POST | `/api/tallies` | Tạo hồ sơ (bắt buộc đủ trường). |
| DELETE | `/api/tallies/{id}` | Xóa hồ sơ (giữ thay đổi MiniDB). |
| POST | `/api/tallies/{id}/inspect` | Đọc và kiểm tra sơ bộ. |
| POST | `/api/tallies/{id}/inspection/confirm` | Xác nhận dữ liệu đầu vào. |
| POST | `/api/tallies/{id}/evaluate` | Chạy đánh giá sơ bộ. |
| GET | `/api/workflows/{id}` | Trạng thái quy trình. |
| PATCH | `/api/workflows/{id}/review-checklist` | Checklist review. |
| GET / PATCH / DELETE | `/api/evaluations/{id}` | Chi tiết / Final Evaluation / xóa hồ sơ. |
| PATCH | `/api/items/{item_id}` | Review một task. |
| GET | `/api/items/{item_id}/amos` | Popup đối chiếu AMOS (cả gợi ý lớp 2–3). |
| GET | `/api/items/{item_id}/add-form` | Giá trị đề xuất cho "Thêm vào Database". |
| POST | `/api/items/{item_id}/add-to-database` | Thêm bản ghi MiniDB và matching lại. |
| GET / PATCH | `/api/amp/{amp_id}` | Đọc / sửa bản ghi MiniDB. |
| GET | `/api/amp-fields` | Danh sách trường form. |
| GET | `/api/amp-changes/export` | Excel thay đổi MiniDB. |
| GET | `/api/evaluations/{id}/report/{kind}` | Important/database/scope. |
| GET | `/api/evaluations/{id}/export` | Xuất Excel. |
| GET | `/api/evaluations/{id}/history` | Lịch sử thay đổi. |
| GET | `/api/tally/{id}/download` | Tải file nguồn. |

`/api/upload` (nạp và đánh giá một bước) đã bỏ; dùng `/api/tallies` + các bước.

## 11. Kiểm thử và checklist trước khi push

```powershell
git status --short
python -m unittest discover -s tests -v
python -m compileall -q app.py wp_app tests
node --check static\app-ver3.js
git diff --check
```

Không commit database, uploads, `.env`, file Excel hoặc dữ liệu khách hàng. Không ghi đè thay đổi chưa commit của người khác.

## 12. Giới hạn hiện tại

- Chưa có đăng nhập/phân quyền; SQLite chỉ phù hợp một tiến trình.
- Check Scope chưa có nguồn Task–Check/Linked Check; TAT nhập tay.
- `static/app-ver3.js` vẫn là một file lớn (đã chia 12 phần có chú thích).
