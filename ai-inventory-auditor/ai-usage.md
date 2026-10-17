# AI usage disclosure

This project uses an LLM (Groq API) at runtime for intent interpretation, tool selection, and natural-language responses. The application code calls the model through `agent/agent_loop.py`; the model does not directly access the CSV files or database. Inventory calculations and audit persistence are performed by deterministic Python services and SQLite.

AI-assisted development was used for code drafting, debugging, and documentation. The team reviewed and adapted generated code, ran local unit tests and the evaluation script, and remains responsible for correctness, security, citations, and final submission. Update this file with the actual tools, prompts, and contributions used by each team member before submission; do not claim tests or manual review that were not performed.

The evaluation metric `faithfulness_proxy` is a simple citation-presence heuristic, not a human-validated semantic faithfulness score.
