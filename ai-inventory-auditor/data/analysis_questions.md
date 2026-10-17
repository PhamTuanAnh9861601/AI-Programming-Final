# Các vấn đề nên khai thác trong AI Inventory Auditor

## 1. Tính toán và lọc trạng thái
- Tính expected_stock = opening_stock + IN POSTED - OUT POSTED.
- So sánh tác động của DRAFT/CANCELLED/REJECTED với POSTED.
- Tính variance = physical_count - expected_stock; phân biệt variance âm/dương/0.

## 2. Áp dụng chính sách và biên ngưỡng
- Kiểm tra abs(variance) = 0, 1, 9, 10 và trên 10.
- So sánh INV-DOC-001 v1.0 với INV-DOC-002 v2.0; dùng metadata ngày/version để chọn chính sách hiện hành.
- Phân biệt priority của phiếu với kết luận về nguyên nhân.

## 3. Dữ liệu thiếu và hiệu chuẩn từ chối
- physical_count rỗng: không tính variance, không tạo phiếu.
- Thiếu đơn giá, danh tính nhân viên, camera, deadline: phải từ chối đúng phần không có bằng chứng.
- Phân biệt “tài liệu không có câu trả lời” với “có số liệu nhưng thiếu một vế để suy luận”.

## 4. Chất lượng dữ liệu
- Kiểm tra transaction_id trùng; đã sửa một ID trùng trong v2 và ghi ở DATASET_CHANGELOG.md.
- Kiểm tra expected_stock âm: SP038, SP040 trong dữ liệu hiện tại; không tự sửa nguồn hoặc kết luận nguyên nhân.
- Kiểm tra transaction quantity > 0, type thuộc IN/OUT, status thuộc tập quy định, product_id tồn tại, ngày trong phạm vi kỳ.
- Cần phân biệt lỗi dữ liệu và sự kiện vận hành thực tế.

## 5. Side effect và verify
- Chỉ tạo phiếu khi user yêu cầu rõ ràng và dữ liệu đủ điều kiện.
- Sau write, gọi read-back bằng đúng audit_id; xác nhận audit_id, product_id và status.
- Thử lỗi write, sai audit_id, read-back không tìm thấy và hết MAX_STEPS.

## 6. Bộ câu hỏi đề xuất cho demo/eval
- Q01–Q10, Q16: câu có thể trả lời dựa trên data/policy.
- Q11–Q15: câu no_answer; câu trả lời đúng phải nêu thiếu dữ liệu, không bịa.
- Testset trong gói là bản khung: kiểm tra `evaluation/evaluate.py` để đồng bộ schema trước khi chạy `make eval`.
