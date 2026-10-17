# AI Inventory Auditor

Agent kiểm toán tồn kho dùng Groq native tool calling, MCP stdio, dịch vụ nghiệp vụ có kiểm soát, và RAG tra cứu tài liệu chính sách.

## Yêu cầu
- Python 3.11+ (khuyến nghị)
- Groq API key có quyền dùng model được cấu hình
- Cài dependencies từ `requirements.txt`

## Cài đặt
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```
Mở `.env`, điền `GROQ_API_KEY`. Không commit `.env` hoặc API key.

## Chạy demo
```powershell
python app.py
```
MCP client chạy server qua stdio, tự discover tools/schema, rồi đưa schema đó cho AgentLoop. Ví dụ câu hỏi đọc-only: `Kiểm tra tồn kho SP001`. Muốn ghi phiếu phải yêu cầu rõ ràng, ví dụ `Tạo phiếu kiểm toán cho SP001 vì có chênh lệch tồn kho`.

## Test và evaluation
```powershell
python -m unittest tests.test_inventory_service tests.test_audit_service tests.test_agent_loop -v
python evaluation/evaluate.py
```
Evaluation dùng `data/tests/testset.jsonl`, đi qua MCP và lưu báo cáo tại `evaluation/results.json`. Bộ test chứa ca tính toán, chính sách nhiều phiên bản, dữ liệu thiếu, suy luận cần nhiều tài liệu và câu cần từ chối. Một số ca có thể thất bại; không sửa kết quả chỉ để đạt 100%.

Test phần RAG/MCP và policy: `python -m unittest tests.test_inventory_tools tests.test_policy_service -v`.

## Flow tra cứu chính sách qua MCP
1. `MCPClient` khởi chạy `mcp_server.server` bằng stdio, gọi `list_tools()` và chuyển schema được discover cho AgentLoop.
2. Agent gọi `search_inventory_policy(query, top_k, search_mode, min_score)`. MCP tool chuyển nguyên tham số sang `InventoryTools`.
3. Tool kiểm tra query, top_k và ngưỡng `min_score` trong [0, 1], sau đó truyền ngưỡng vào `RAGPipeline.retrieve`. Mặc định hybrid và `min_score=0.25`; có thể yêu cầu dense hoặc ngưỡng khác.
4. Retrieval chấm điểm trên toàn bộ corpus, gồm mọi version. Điểm thấp hơn ngưỡng bị loại ngay ở retrieval; nếu không còn đoạn phù hợp, tool trả evidence rỗng. Kết quả giữ `doc_id`, version, date, chunk và score để Agent đối chiếu xung đột phiên bản (quy tắc chọn bản hiện hành vẫn căn cứ date trong tài liệu).
5. Agent trả lời dựa trên evidence và trích doc_id. Ngưỡng là bộ lọc liên quan sơ bộ; không chứng minh nội dung câu trả lời được tài liệu hỗ trợ về mặt ngữ nghĩa.

## Makefile
Trên môi trường có GNU Make: `make setup`, `make demo`, `make eval`, `make test`. Trên Windows PowerShell, các lệnh Python phía trên tương đương và không yêu cầu cài Make.

## Thiết kế
- `agent/agent_loop.py`: vòng lặp tool calling, quyền ghi, giới hạn bước, retry/timeout do client API cấu hình, log usage.
- `tools/mcp_client.py`, `mcp_server/server.py`: MCP stdio và schema discovery.
- `tools/inventory_tools.py`: adapter nghiệp vụ và search policy RAG.
- `business/`, `storage/`: tính tồn kho, kiểm soát phiếu, SQLite và verify sau ghi.
- `retrieval/`, `data/documents/`: chunking ký tự với overlap 30 ký tự để giảm mất ngữ cảnh ở ranh giới; dense cosine và hybrid BM25 + vector.

Lý do chọn chunking: tài liệu chính sách ngắn, có các điều khoản đánh số và thường được truy vấn theo từng quy tắc. Chunk 150 ký tự giúp kết quả tập trung vào điều khoản liên quan thay vì đưa cả tài liệu dài vào context. Overlap 30 ký tự giữ lại một phần câu ở ranh giới chunk để không cắt rời điều kiện và kết luận. Metadata của tài liệu được gắn vào từng chunk để câu trả lời có thể trích đúng doc_id, version và date.
- `evaluation/`: pass/fail theo tiêu chí, recall doc_id và faithfulness proxy (tỷ lệ câu có trích doc_id, không phải phép đo entailment/faithfulness ngữ nghĩa).

## Log và bảo mật
Mỗi lượt chạy ghi `logs/agent_runs.jsonl`, `logs/agent_runs_pretty.json` và một JSONL riêng trong `logs/per_run/`. Log gồm prompt/completion/total tokens, `max_prompt`, tool arguments/results và câu trả lời. Kiểm tra log trước khi nộp, loại bỏ thông tin nhạy cảm nếu có. Không đưa `.env`, database runtime hoặc dữ liệu cá nhân vào Git.
