# Bàn giao tiếp tục phát triển trên Codex

Tài liệu này là điểm vào nhanh khi chuyển repository sang máy công ty hoặc mở một phiên Codex mới. Cập nhật gần nhất: 12/10/2026 (bản hợp nhất Ver3 + MPD key).

## 1. Mục tiêu dự án

Xây dựng công cụ nội bộ giúp VAECO tiếp nhận Tally Sheet, đối chiếu AMOS/Customer AMP, review kết quả Workpack theo quy trình năm bước và xuất Excel có thể truy vết.

Phiên bản hiện tại là demo chức năng, chưa phải hệ thống production (chưa có authentication, phân quyền, migration framework, CI/CD, nhiều người dùng đồng thời).

## 2. Trạng thái bàn giao

- Backend là package `wp_app`; lệnh `python -m uvicorn app:app` vẫn hoạt động.
- Parser đăng ký qua `wp_app/adapters.py`; mẫu Tally do người dùng chọn ở bước 1 (`adapter_for_upload`).
- **Matching lớp 1 = MPD key** trong `wp_app/mpd_matching.py`; cấu hình trong `wp_app/matching_config.py`.
- Lớp 2–3 (tiền tố, Title) trong `wp_app/matching.py` + `services.lookup_amp(include_exact=False)`; chỉ chạy khi lớp 1 không có kết quả, không gán MHR.
- Trạng thái lưu bằng mã `AUTO_MATCH / REVIEW_REQUIRED / NOT_FOUND / NOT_APPLICABLE`, hiển thị tiếng Việt.
- Popup AMOS và Thêm/Sửa bản ghi MiniDB trong `wp_app/minidb.py`, route ở `wp_app/api/records.py`.
- `MATCH_LOGIC_VERSION = 5`.
- Frontend: `static/app-ver3.js` (12 phần có chú thích). CSS của Ver3 giữ nguyên, phần bổ sung nằm ở cuối `app.css` và `grid.css` (khối "Merged features").
- `data/` không được Git theo dõi.

## 3. Các file cần đọc trước khi sửa

1. `README.md` — cài đặt, kiến trúc, quy tắc matching, API.
2. `wp_app/config.py`, `wp_app/matching_config.py`.
3. `wp_app/adapters.py`, `wp_app/parsers.py`.
4. `wp_app/mpd_matching.py` (lớp 1) và `wp_app/matching.py` (lớp 2–3).
5. `wp_app/services.py` — workflow, `populate_evaluation_items`, migration.
6. `wp_app/minidb.py` — popup và MiniDB.
7. `tests/` — contract hiện tại.

## 4. Dữ liệu không đi qua Git

`.gitignore` loại trừ `data/`, `*.db`, `*.xlsx`, `.env`, `.venv/`. Clone repository sẽ không có `data/wp_demo.db`, `data/uploads/`, hồ sơ và lịch sử review. Muốn giữ đúng trạng thái dữ liệu, sao chép riêng qua kênh nội bộ được phép. File AMOS/sample đặt ở thư mục cha: `DATABASE/` và `TALLY SHEET KHACH HANG/`.

Database cũ của nhánh MPD key (bản `app.py` một file) dùng được trực tiếp: đặt vào `data/wp_demo.db`, khởi động lại; startup tự thêm cột, dựng lại MiniDB nếu thiếu cột, chuyển nhãn trạng thái cũ sang mã mới và tạo các bước workflow.

## 5. Khởi tạo trên máy công ty

```powershell
git clone <repository-url>
cd wp_demo_app_ver3
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m uvicorn app:app --reload --port 8001
```

## 6. Prompt khởi động cho Codex

```text
Hãy tiếp tục phát triển dự án VAECO Workpack Evaluation trong repository hiện tại.

Trước khi sửa mã:
1. Đọc đầy đủ README.md và BAN_GIAO_CODEX.md.
2. Kiểm tra git status và bảo toàn mọi thay đổi chưa commit.
3. Đọc wp_app: config.py, matching_config.py, adapters.py, mpd_matching.py, matching.py, services.py, minidb.py và router liên quan.
4. Chạy python -m unittest discover -s tests -v để lấy baseline.
5. Không đưa data/, file Excel nghiệp vụ, database, uploads hoặc thông tin nhạy cảm vào Git.

Khi triển khai yêu cầu mới:
- Lớp 1 (MPD key) là luồng matching chính; lớp 2–3 chỉ là gợi ý, không gán MHR.
- Quy tắc theo khách hàng đặt trong matching_config.py, không viết cứng mã khách hàng trong code.
- Đặt business logic trong service/matching/parser/minidb, không dồn vào route hoặc app.py.
- Mọi thay đổi MiniDB phải ghi amp_change; không bao giờ ghi vào hệ thống AMOS.
- Bổ sung test hồi quy cho mọi thay đổi matching, parser hoặc schema.
- Giữ tương thích lệnh uvicorn app:app.
- Sau khi hoàn tất, chạy tests, compileall, node --check và git diff --check.
- Cập nhật README.md và BAN_GIAO_CODEX.md nếu kiến trúc, API, cấu hình hoặc giới hạn thay đổi.

Trước tiên hãy báo lại: trạng thái Git, kết quả baseline tests, module liên quan và rủi ro bạn thấy; sau đó mới sửa mã.
```

## 7. Quy ước phát triển

- `app.py` chỉ là compatibility entry point.
- Route chỉ xác thực request, gọi service và định dạng response.
- Không nhúng đường dẫn máy cá nhân; dùng `config.py` và biến môi trường.
- Thay đổi kết quả review phải có lý do và ghi `change_log`; thay đổi MiniDB ghi `amp_change`.
- Migration phải chạy lặp lại an toàn (cột mới thêm vào `MERGED_MIGRATIONS` hoặc danh sách migration của `init_db`).
- Không tự động gán MHR cho candidate lớp 2 hoặc lớp 3.
- Không làm lẫn model A320 với A321 ở lớp 2–3 (`aircraft_rank`); lớp 1 lọc theo họ tàu (`aircraft_family`: 32S/350/787/ATR).
- Khách hàng tìm Customer AMP trước ALL AMP Task cấu hình trong `CUSTOMER_FIRST` (mặc định DLH + A350).
- Trường nhận diện bản ghi MiniDB (`NATURAL_KEY_FIELDS`) không được sửa.

## 8. Kiểm thử

| File | Nội dung |
|---|---|
| `tests/test_app_structure.py` | Registry adapter; contract đường dẫn API; không còn `/api/upload`. |
| `tests/test_matching.py` | Hàm chung, `lookup_amp` lớp 1–3, parser regression trên file mẫu (tự bỏ qua nếu thiếu file). |
| `tests/test_mpd_matching.py` | MPD key, LH/RH, dòng VietJet được matching, thứ tự nguồn theo cấu hình, HVN trước AMP Date, chia item ENG #1/#2, `REVIEW_REQUIRED` của lớp 1, gợi ý lớp 2 không MHR, `NOT_APPLICABLE`, Thêm vào Database + matching lại, Sửa bản ghi (trường khóa), popup. |

Checklist sau mỗi thay đổi:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py wp_app tests
node --check static\app-ver3.js
git diff --check
git status --short
```

## 9. Điểm mở rộng ưu tiên

1. Tách `static/app-ver3.js` thành module.
2. Authentication và role reviewer/approver/admin.
3. Migration có version (Alembic hoặc tương đương).
4. Nguồn Task–Check/Linked Check cho Check Scope.
5. Database Workpack lịch sử để đề xuất TAT.
6. Integration test HTTP và CI.
7. PostgreSQL nếu nhiều người dùng đồng thời.

## 10. Rủi ro cần nhớ

- File Excel nguồn có thể đổi tên cột/cấu trúc; parser phải báo lỗi rõ và có test mới.
- Đổi logic matching → tăng `MATCH_LOGIC_VERSION`; hồ sơ không có thao tác thủ công sẽ được matching lại khi khởi động.
- MiniDB chỉ dựng lại khi thiếu cột; khi đó bản ghi thủ công được giữ và các lần sửa được áp dụng lại theo khóa tự nhiên.
- Sao lưu `data/` trước migration hoặc xóa dữ liệu.
- Chỉ dùng trong môi trường tin cậy (upload chỉ kiểm tra đuôi file và dung lượng).
