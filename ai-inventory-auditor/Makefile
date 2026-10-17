PYTHON ?= python
VENV_PYTHON ?= .venv/bin/python

.PHONY: setup demo eval test clean-logs
setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# Run with: make demo PYTHON=python (Windows) or make demo PYTHON=.venv/bin/python
demo:
	$(PYTHON) app.py

eval:
	$(PYTHON) evaluation/evaluate.py

test:
	$(PYTHON) -m unittest tests.test_inventory_service tests.test_audit_service tests.test_agent_loop tests.test_inventory_tools tests.test_policy_service tests.test_metrics -v

clean-logs:
	$(PYTHON) -c "import shutil; shutil.rmtree('logs', ignore_errors=True)"
