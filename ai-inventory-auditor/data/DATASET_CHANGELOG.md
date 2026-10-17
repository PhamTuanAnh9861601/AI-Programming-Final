# Dataset v2 — changelog

## Giữ nguyên
- `products.csv`: giữ nguyên 44 sản phẩm và physical_count gốc.
- `sample_audit_history.csv`: giữ nguyên lịch sử mẫu, không dùng nó làm bằng chứng rằng runtime đã tạo phiếu.
- 8 tài liệu gốc INV-DOC-001 đến INV-DOC-008 được giữ nguyên.

## Sửa có kiểm soát
- `transactions.csv`: phát hiện transaction_id trùng `TX90249` ở hai sản phẩm. Đã đổi ID của giao dịch OUT thuộc SP003 từ `TX90249` thành `TX90255`; product_id, type, quantity, date và status giữ nguyên. Việc này không đổi phép tính tồn kho.

## Bổ sung
- `data_quality_issues.csv`: danh sách sản phẩm có tồn dự kiến âm sau khi chỉ tính giao dịch POSTED. Đây là bất thường cần điều tra, không phải lý do tự sửa số liệu.
- Thêm `INV-DOC-009`, `INV-DOC-010`, `INV-DOC-011`, mỗi tài liệu có DOC_ID, TITLE, VERSION, DATE, OWNER.
- `analysis_questions.md`: các nhóm vấn đề có thể khai thác từ dữ liệu.
- `tests/testset.jsonl`: 16 câu kiểm thử gợi ý, gồm 5 câu no_answer. Cần đồng bộ field names với `evaluation/evaluate.py` hiện tại trước khi coi là chạy được trực tiếp.

## Phát hiện sơ bộ
- Products: 44; transactions: 245.
- Tồn dự kiến âm: 2 sản phẩm: SP038, SP040.
- Không tự suy ra nguyên nhân chênh lệch chỉ từ tồn kho.
