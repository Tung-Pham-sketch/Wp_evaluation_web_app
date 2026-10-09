# VAECO Workpack Evaluation

Ứng dụng demo nội bộ để quản lý Tally Sheet, đối chiếu dữ liệu AMOS, review và tổng hợp đánh giá Workpack.

## Chạy ứng dụng

```powershell
cd "01. PROJECT\01. BAI TOAN DANH GIA WP\DEMO DE TAI\wp_demo_app"
python -m uvicorn app:app --reload --port 8000
```

Mở `http://127.0.0.1:8000`. Lần chạy đầu ứng dụng nhập dữ liệu AMOS vào SQLite; có thể mất khoảng một phút.

## Dữ liệu

- Nguồn AMOS được đọc từ thư mục `../DATABASE/`.
- File mẫu được đọc từ `../TALLY SHEET KHACH HANG/`.
- Database, file upload và báo cáo xuất ra được lưu trong `data/`.
- Xóa `data/wp_demo.db` để tạo lại MiniDB từ đầu.

## Phạm vi demo

- Hỗ trợ Tally VietJet và Lufthansa.
- Matching mã chính xác, không phân biệt chữ hoa/thường.
- MHR chỉ lấy từ task đã khớp; task chưa khớp không tự được gán MHR.
- Important Job lấy từ `Classification = Watch Item` và cho phép review thủ công có lý do.
- TAT nhập thủ công; chưa có logic đề xuất do chưa có database WP mẫu.

