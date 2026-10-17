PYTHON ?= python
VENV_PYTHON ?= .venv/bin/python

.PHONY: setup demo eval eval-failed eval-regrade eval-retrieval test clean-logs
setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# Run with: make demo PYTHON=python (Windows) or make demo PYTHON=.venv/bin/python
demo:
	$(PYTHON) app.py

eval:
	$(PYTHON) evaluation/evaluate.py

# Đánh giá RAG (dense vs hybrid, line vs fixed) — không tốn token LLM.
eval-retrieval:
	$(PYTHON) evaluation/eval_retrieval.py

# Chỉ chạy lại các câu FAILED/ERROR trong results.json (tốn ít token).
eval-failed:
	$(PYTHON) evaluation/evaluate.py --failed

# Chấm lại câu trả lời đã lưu bằng bộ chấm hiện tại, KHÔNG gọi API (0 token).
eval-regrade:
	$(PYTHON) evaluation/evaluate.py --regrade

test:
	$(PYTHON) -m unittest tests.test_inventory_service tests.test_audit_service tests.test_agent_loop tests.test_metrics tests.test_policy_service tests.test_model tests.test_evaluate_cli tests.test_retrieval -v

clean-logs:
	$(PYTHON) -c "import shutil; shutil.rmtree('logs', ignore_errors=True)"
