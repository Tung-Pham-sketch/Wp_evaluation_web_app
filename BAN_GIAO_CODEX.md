# Bàn giao tiếp tục phát triển trên Codex

Tài liệu này là điểm vào nhanh khi chuyển repository sang máy công ty hoặc mở một phiên Codex mới. Cập nhật gần nhất: 11/10/2026.

## 1. Mục tiêu dự án

Xây dựng công cụ nội bộ giúp VAECO tiếp nhận Tally Sheet, đối chiếu AMOS/Customer AMP, review kết quả Workpack theo quy trình năm bước và xuất Excel có thể truy vết.

Phiên bản hiện tại là demo chức năng. Chưa được xem là hệ thống production vì chưa có authentication, phân quyền, migration framework, CI/CD và cơ chế đồng thời nhiều người dùng.

## 2. Trạng thái bàn giao

- Backend đã tách khỏi file đơn thành package `wp_app`.
- Lệnh chạy cũ `python -m uvicorn app:app` vẫn hoạt động.
- Parser được đăng ký qua `wp_app/adapters.py`.
- Matching ba lớp nằm trong `wp_app/matching.py` và `wp_app/services.py`.
- API được chia thành dashboard, tallies/workflow và evaluations/report.
- Frontend hiện dùng `static/app-ver3.js`; không còn `static/app.js` cũ.
- Database và uploads nằm trong `data/`, không được Git theo dõi.
- Bộ kiểm thử bao phủ matching, parser sample, adapter registry và contract đường dẫn API.

## 3. Các file cần đọc trước khi sửa

Theo thứ tự:

1. `README.md` — cài đặt, kiến trúc, API, nghiệp vụ và cách mở rộng.
2. `wp_app/config.py` — vị trí dữ liệu và biến môi trường.
3. `wp_app/adapters.py` — registry customer/parser.
4. `wp_app/matching.py` — thuật toán và ngưỡng matching.
5. `wp_app/services.py` — workflow và orchestration.
6. Router liên quan trong `wp_app/api/`.
7. `tests/` — contract hiện tại trước khi thay đổi hành vi.

## 4. Dữ liệu không đi qua Git

`.gitignore` loại trừ toàn bộ `data/`. Vì vậy clone repository trên máy công ty sẽ không có:

- `data/wp_demo.db`.
- `data/uploads/`.
- Các hồ sơ và lịch sử review hiện tại.

Nếu cần tiếp tục đúng trạng thái dữ liệu hiện tại, hãy sao chép riêng hai mục trên bằng kênh nội bộ được phê duyệt. Không tải dữ liệu khách hàng lên GitHub công khai.

Nếu chỉ cần source code và database mới, không cần sao chép `data/`; ứng dụng sẽ tạo lại khi khởi động.

Các file tham chiếu AMOS và sample mặc định được tìm tại:

```text
<thư mục cha repository>/DATABASE/
<thư mục cha repository>/TALLY SHEET KHACH HANG/
```

Xem tên file cụ thể trong README.

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

Nếu dữ liệu phải đặt ngoài repository:

```powershell
$env:WP_DATA_DIR = 'D:\VAECO_DATA\wp_demo_ver3'
$env:WP_SKIP_SEED_SAMPLES = '1'
python -m uvicorn app:app --reload --port 8001
```

## 6. Prompt khởi động cho Codex

Sao chép nguyên khối dưới đây vào phiên Codex mới:

```text
Hãy tiếp tục phát triển dự án VAECO Workpack Evaluation trong repository hiện tại.

Trước khi sửa mã:
1. Đọc đầy đủ README.md và BAN_GIAO_CODEX.md.
2. Kiểm tra git status và bảo toàn mọi thay đổi chưa commit.
3. Đọc cấu trúc wp_app, đặc biệt config.py, adapters.py, matching.py, services.py và router liên quan.
4. Chạy python -m unittest discover -s tests -v để lấy baseline.
5. Không đưa data/, file Excel nghiệp vụ, database, uploads hoặc thông tin nhạy cảm vào Git.

Khi triển khai yêu cầu mới:
- Đặt business logic trong service/matching/parser, không dồn vào route hoặc app.py.
- Parser/customer mới phải đăng ký qua wp_app/adapters.py.
- Bổ sung test hồi quy cho mọi thay đổi matching, parser hoặc schema.
- Giữ tương thích lệnh uvicorn app:app.
- Sau khi hoàn tất, chạy tests, compileall, node --check và git diff --check.
- Cập nhật README.md và BAN_GIAO_CODEX.md nếu kiến trúc, API, cấu hình hoặc giới hạn thay đổi.

Trước tiên hãy báo lại: trạng thái Git, kết quả baseline tests, module liên quan và rủi ro bạn thấy; sau đó mới sửa mã.
```

## 7. Quy ước phát triển

- `app.py` chỉ là compatibility entry point, không thêm business logic vào đây.
- Route chỉ xác thực request, gọi service và định dạng response.
- Logic thuần nên nằm trong `matching.py`, `parsers.py` hoặc service phù hợp.
- Không nhúng đường dẫn máy cá nhân vào mã; dùng `config.py` và biến môi trường.
- Mọi thao tác thay đổi kết quả review phải có lý do và ghi `change_log`.
- Migration phải chạy lặp lại an toàn trên database hiện hữu.
- Không tự động gán MHR cho candidate lớp 2 hoặc lớp 3.
- Không làm lẫn model A320 với A321 khi candidate không thuộc family A32S phù hợp.
- DLH A350 chỉ matching Customer AMP đúng DLH/A350.

## 8. Checklist sau mỗi thay đổi

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py wp_app tests
node --check static\app-ver3.js
git diff --check
git status --short
```

Nếu thay đổi API, mở `/docs` và chạy smoke test các endpoint liên quan. Nếu thay đổi export, tải file Excel và mở kiểm tra các sheet, cột, trạng thái draft/chính thức.

## 9. Điểm mở rộng ưu tiên

1. Tách `static/app-ver3.js` thành module theo dashboard, workflow, grid và API client.
2. Bổ sung authentication và role reviewer/approver/admin.
3. Chuyển migration SQLite sang Alembic hoặc công cụ versioned tương đương.
4. Bổ sung nguồn Task–Check/Linked Check cho Check Scope.
5. Xây dựng database Workpack lịch sử để đề xuất TAT.
6. Bổ sung integration test HTTP tự động và CI trên GitHub.
7. Chuyển sang PostgreSQL nếu triển khai nhiều người dùng đồng thời.

## 10. Rủi ro cần nhớ

- Source Excel có thể đổi tên cột hoặc cấu trúc block; parser phải fail rõ ràng và có fixture/test mới.
- Thay đổi matching có thể làm thay đổi hàng nghìn kết quả cũ; cân nhắc tăng `MATCH_LOGIC_VERSION` và migration.
- Startup chuẩn hóa `stored_path` về đường dẫn tương đối trong `data/`; vẫn phải sao chép đủ `data/uploads/` nếu muốn giữ file nguồn.
- Database SQLite và file upload phải được sao lưu trước khi migration hoặc xóa dữ liệu.
- Ứng dụng chưa có cơ chế chống upload độc hại ngoài giới hạn extension và dung lượng; chỉ dùng trong môi trường tin cậy.

## 11. Tiêu chí hoàn thành một nhánh phát triển

- Yêu cầu nghiệp vụ có test hoặc bằng chứng kiểm thử.
- Không có lỗi cú pháp Python/JavaScript.
- API cũ liên quan vẫn hoạt động hoặc có migration/documentation rõ ràng.
- Không có dữ liệu runtime/nhạy cảm trong diff.
- README và file bàn giao không bị lỗi thời.
- `git diff --check` sạch.
