# Checklist trước khi nộp

- [ ] Cài dependencies bằng `python -m pip install -r requirements.txt`.
- [ ] Tạo `.env` từ `.env.example` và thêm Groq API key; không commit `.env`.
- [ ] Chạy unit tests.
- [ ] Chạy `python evaluation/evaluate.py` qua MCP; xem và phân tích ít nhất một ca FAILED nếu có, không chỉnh số liệu để ép pass 100%.
- [ ] Chạy app thật ít nhất 3 lượt để tạo `logs/agent_runs.jsonl`, `logs/agent_runs_pretty.json` và `logs/per_run/*.jsonl`; kiểm tra các trường token usage và `max_prompt`. Không nộp log giả.
- [ ] Nếu cần báo cáo chi phí tiền tệ, cập nhật `GROQ_INPUT_USD_PER_MILLION` và `GROQ_OUTPUT_USD_PER_MILLION` theo bảng giá hiện hành của model đang dùng.
- [ ] Cập nhật `ai-usage.md` cho đúng công cụ AI, phần code được hỗ trợ và đóng góp thực tế của từng thành viên.
- [ ] Chạy `git status`, commit các file cần thiết, và nộp/push repository thật nếu yêu cầu lịch sử `.git`. ZIP tải xuống không mang lịch sử Git.
