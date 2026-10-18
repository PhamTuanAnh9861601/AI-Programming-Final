# AI Inventory Auditor

Agent kiểm toán tồn kho dùng Groq native tool calling, MCP stdio, dịch vụ nghiệp vụ có kiểm soát, và RAG tra cứu tài liệu chính sách.

## Yêu cầu
- Python 3.11 trở lên
- GNU Make
- Groq API key có quyền dùng model được cấu hình

## Chuẩn bị và chạy demo
Tạo `.env` từ mẫu rồi điền `GROQ_API_KEY` trước khi chạy. Không commit `.env` hoặc API key.

```powershell
Copy-Item .env.example .env
# Mở .env và điền GROQ_API_KEY
make setup && make demo
```

Lệnh demo chạy `app.py`; MCP client khởi chạy server qua stdio, tự discover tools/schema rồi chuyển schema cho AgentLoop. Câu hỏi đọc-only mẫu: `Kiểm tra tồn kho SP001`. Muốn tạo phiếu, cần yêu cầu rõ ràng, ví dụ `Tạo phiếu kiểm toán cho SP001 vì có chênh lệch tồn kho`.

## Đánh giá

```powershell
make eval
make test
make eval-retrieval
```

`make eval` đọc `tests/testset.jsonl` (18 câu, gồm 6 câu `no_answer`) và lưu kết quả vào `evaluation/results.json`. `make eval-retrieval` so sánh dense/hybrid và line/fixed trên cùng testset, không gọi LLM. Các kết quả đã lưu là bản chạy thực tế; chạy lại evaluation cần API key và sẽ thay thế kết quả hiện tại. Không sửa số liệu để ép pass 100%.

## Thiết kế
- `agent/agent_loop.py`: vòng lặp tool calling, quyền ghi, giới hạn bước, retry/timeout, log usage.
- `tools/mcp_client.py`, `mcp_server/server.py`: MCP stdio và schema discovery động.
- `tools/inventory_tools.py`: adapter nghiệp vụ và tra cứu RAG.
- `business/`, `storage/`: tính tồn kho, kiểm soát phiếu, SQLite và verify sau ghi.
- `retrieval/`, `data/documents/`: mặc định chia theo dòng để giữ mỗi quy tắc chính sách nguyên vẹn; chế độ `fixed` (150 ký tự, overlap 30) dùng để so sánh. Hai chế độ truy vấn là dense cosine và hybrid BM25 + vector. Mô hình embedding mặc định là `all-MiniLM-L6-v2`; kết quả retrieval đã lưu ghi nhận mô hình này. Tool tra cứu lọc theo phiên bản mới nhất bằng metadata và trả tối đa 5 đoạn bằng chứng.
- `evaluation/`: pass/fail theo tiêu chí, recall doc_id và faithfulness proxy. Proxy là chỉ số tự động sơ bộ, không thay thế đánh giá ngữ nghĩa.
- `logs/per_run/`: ba log JSONL mẫu từ các lượt chạy thực tế, gồm tra cứu, từ chối khi thiếu bằng chứng và tạo phiếu có bước đọc lại xác minh. Mỗi log có timestamp, tool args/kết quả và usage.

## Dữ liệu và bảo mật
Dữ liệu là dữ liệu giả lập cho bài tập. `.env`, database SQLite runtime, cache Python và kết quả chạy dở không thuộc gói nộp. Log mẫu đã chọn cần được rà soát trước khi chia sẻ công khai.
