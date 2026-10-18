# AI Usage Disclosure — AI Inventory Auditor (Group 10)

## 1. Summary

Most of this project was designed, written and debugged by the team by hand. By our own estimate, **about 60–70% of the work is our own**. AI was used as an assistant only for the areas listed in section 3. Every AI-assisted part was read, run and adapted by the team, and each member can explain the files they are responsible for.

The application also calls an LLM at runtime (Groq, `openai/gpt-oss-20b`) for tool selection and answer wording. This is a product feature, not development assistance. The model never reads the CSV files or the database directly: stock calculations and audit-ticket writes are done by deterministic Python services and SQLite.

## 2. AI tools used

| Tool | Used for |
|---|---|
| ChatGPT | Suggestions for the five areas in section 3 |
| Claude | Suggestions for the five areas in section 3; drafting the report (structure and text, using the team's code, logs and evaluation results) and this disclosure file |
| OpenAI Codex | Final review and packaging pass only: checking the submission, aligning README / report / evaluation paths with the saved results |

## 3. Where AI was used

| # | Area | Files | How AI helped |
|---|---|---|---|
| 1 | Test cases | `tests/*.py`, `tests/testset.jsonl` | Suggested test cases and edge cases (missing `physical_count`, variance 0 / 9 / 10, DRAFT vs POSTED, no_answer questions) |
| 2 | Flow skeleton | `agent/agent_loop.py` | Suggested the outline of the flow (question → tool call → observation → answer, verify after write). Used as a suggestion only |
| 3 | Database data | `data/products.csv`, `data/transactions.csv`, `data/sample_audit_history.csv` | Helped produce and structure the sample data |
| 4 | Database-write business logic | `business/audit_service.py`, `storage/audit_repository.py`, `storage/database.py` | Helped with the rules and code for creating an audit ticket and saving it to SQLite (guards, idempotency, read-back) |
| 5 | System prompt file | `agent/prompt/system_prompt.txt` | Helped draft the prompt rules |
| 6 | Report | `report.docx` | Claude drafted the structure and text from the team's code, logs and results; the team added its own screenshots, corrected and verified the content |

Written by the team without AI assistance: the rest of the agent loop (step limit, write gate, retry, logging), the RAG pipeline (`retrieval/*`), the MCP server and client (`mcp_server/*`, `tools/*`), and the evaluation scripts (`evaluation/*`).

## 4. Prompts

We did not keep the verbatim prompts. Representative summaries:

1. Test cases: "Suggest test cases for an inventory audit agent, including missing data, boundary values and questions with no answer."
2. Flow: "Suggest the flow for an agent that answers inventory questions with tools and creates an audit ticket, then verifies it."
3. Data: "Create sample products and transactions with POSTED / DRAFT / CANCELLED / REJECTED statuses."
4. Database write: "Write the logic to create an audit ticket in SQLite and read it back to verify."
5. System prompt: "Write system-prompt rules for an inventory audit agent: cite sources, refuse when evidence is missing, write only on explicit request."

## 5. Human review and responsibility

- The team reviewed, ran and modified the AI-assisted parts. We ran `make test` and `make eval`; results are in `evaluation/results.json`.
- We do not claim any file as AI-generated beyond what is listed above.
- The metric `faithfulness_proxy` is a citation-presence heuristic, not a human-validated faithfulness score.

## 6. Per-member declaration

| Member | AI-assisted parts | Parts written by the member |
|---|---|---|
| Phạm Tuấn Anh (24110076) | Areas 1–5 in section 3: test case suggestions, flow outline (as a suggestion), sample data, audit-ticket write logic, system prompt drafting | Agent loop details, business logic, storage, evaluation, tests, datasets, app/config; reviewed and adapted all AI suggestions |
| Hoàng Thị Thu Trang (24110139) | None. The areas in section 3 are outside her modules | Retrieval, `eval_retrieval.py`, MCP server, MCP tools/client |