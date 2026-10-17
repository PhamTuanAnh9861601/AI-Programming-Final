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
python -m unittest tests.test_inventory_service tests.test_audit_service tests.test_agent_loop tests.test_metrics tests.test_policy_service tests.test_model tests.test_evaluate_cli tests.test_retrieval -v
python evaluation/evaluate.py
```
Evaluation dùng `data/tests/testset.jsonl`, đi qua MCP và lưu báo cáo tại `evaluation/results.json`. Bộ test chứa ca tính toán, chính sách nhiều phiên bản, dữ liệu thiếu, suy luận cần nhiều tài liệu và câu cần từ chối. Một số ca có thể thất bại; không sửa kết quả chỉ để đạt 100%.

## Makefile
Trên môi trường có GNU Make: `make setup`, `make demo`, `make eval`, `make test`. Trên Windows PowerShell, các lệnh Python phía trên tương đương và không yêu cầu cài Make.

## Thiết kế
- `agent/agent_loop.py`: vòng lặp tool calling, quyền ghi, giới hạn bước, retry/timeout do client API cấu hình, log usage.
- `tools/mcp_client.py`, `mcp_server/server.py`: MCP stdio và schema discovery.
- `tools/inventory_tools.py`: adapter nghiệp vụ và search policy RAG.
- `business/`, `storage/`: tính tồn kho, kiểm soát phiếu, SQLite và verify sau ghi.
- `retrieval/`, `data/documents/`: **chunking theo dòng** (mỗi quy tắc đánh số của chính sách là một đoạn nguyên vẹn, ≤ ~165 ký tự). Lý do: cắt cố định 150 ký tự làm đứt giữa từ và giữa quy tắc (ví dụ `audit_id` bị cắt thành `udit_id`), khiến BM25 mất từ khóa và đoạn đúng bị xếp hạng thấp; chế độ `fixed` vẫn có sẵn để so sánh (`CHUNK_MODE=fixed`). Hai chế độ truy vấn: dense cosine và hybrid BM25 + vector. Tool tra cứu chỉ lấy bản chính sách mới nhất theo metadata `date` và luôn trả tối thiểu 5 đoạn.
- `evaluation/eval_retrieval.py`: đánh giá RAG riêng (hit@k, recall@k, MRR; dense vs hybrid; line vs fixed) và hiệu chỉnh `RETRIEVAL_MIN_SCORE`, không gọi LLM nên không tốn token: `python evaluation/eval_retrieval.py`.
- `mcp_server/second_client.py`: client MCP thứ hai viết bằng JSON-RPC thô (không dùng mcp SDK), tự khám phá tool và kiểm tra stdout của server chỉ chứa JSON-RPC: `python -m mcp_server.second_client`.
- `evaluation/`: pass/fail theo tiêu chí, recall doc_id và faithfulness proxy. Proxy chỉ là chỉ số tự động sơ bộ, không thay thế đánh giá ngữ nghĩa của người chấm.

## Log và bảo mật
Mỗi lượt chạy ghi `logs/agent_runs.jsonl`, `logs/agent_runs_pretty.json` và một JSONL riêng trong `logs/per_run/`. Log gồm prompt/completion/total tokens, `max_prompt`, tool arguments/results và câu trả lời. Kiểm tra log trước khi nộp, loại bỏ thông tin nhạy cảm nếu có. Không đưa `.env`, database runtime hoặc dữ liệu cá nhân vào Git.
