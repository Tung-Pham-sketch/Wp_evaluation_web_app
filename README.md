# VAECO Workpack Evaluation · Ver3

Ứng dụng demo nội bộ để quản lý Tally Sheet, đối chiếu dữ liệu AMOS, review và tổng hợp đánh giá Workpack.

## Chạy ứng dụng

```powershell
cd "01. PROJECT\01. BAI TOAN DANH GIA WP\DEMO DE TAI\wp_demo_app_ver3"
python -m uvicorn app:app --reload --port 8001
```

Mở `http://127.0.0.1:8001`. Phiên bản gốc tiếp tục chạy độc lập tại cổng `8000`.

## Quy trình đánh giá 5 bước

1. Tiếp nhận Tally Sheet và metadata.
2. Đọc, kiểm tra sơ bộ rồi xác nhận đầu vào.
3. Chạy đánh giá sơ bộ và đối chiếu AMOS.
4. Review Detailed Task List, Important Jobs, task thiếu database và Check Scope.
5. Hoàn thiện Final Evaluation, phê duyệt thủ công và xuất Excel.

Mỗi bước hoàn thành tương ứng 20% tiến độ. Có thể chuyển tự do giữa các bước; ứng dụng sẽ cảnh báo khi dữ liệu đầu vào chưa sẵn sàng. Báo cáo xuất trước khi hoàn tất được đánh dấu `BẢN NHÁP` và có tiền tố `DRAFT_`.

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

