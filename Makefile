PYTHON ?= python3
VENV_PYTHON := .venv/bin/python

.PHONY: setup test focused-test acquisition-demo engine-demo edgar-offline sec-api-offline task005-proof task006-proof lint format-check typecheck import-check docs-check baseline-check build validate review-package

setup:
	$(PYTHON) -m venv .venv

test: setup
	$(VENV_PYTHON) -m unittest discover -s tests -v

focused-test: setup
	$(VENV_PYTHON) -m unittest tests.test_acquisition -v

acquisition-demo: setup
	$(VENV_PYTHON) scripts/acquisition_operator.py demo

engine-demo: setup
	$(VENV_PYTHON) scripts/verify_engine.py end-to-end

edgar-offline: setup
	env -u RFI_SEC_USER_AGENT $(VENV_PYTHON) scripts/verify_edgar.py

sec-api-offline: setup
	env -u SEC_API_IO_API_KEY $(VENV_PYTHON) scripts/verify_sec_api.py

task005-proof: setup
	$(VENV_PYTHON) scripts/task005_operator.py fixture-proof

task006-proof: setup
	$(VENV_PYTHON) scripts/task006_browser.py fixture-proof

lint: setup
	$(VENV_PYTHON) scripts/quality.py lint

format-check: setup
	$(VENV_PYTHON) scripts/quality.py format

typecheck: setup
	$(VENV_PYTHON) scripts/quality.py typecheck

import-check: setup
	PYTHONPATH=src $(VENV_PYTHON) -c "import rfi; print(rfi.__version__)"

docs-check: setup
	$(VENV_PYTHON) scripts/check_docs.py

baseline-check: setup
	$(VENV_PYTHON) scripts/check_baseline.py

build: setup
	$(VENV_PYTHON) scripts/build_source_archive.py

validate: test acquisition-demo engine-demo edgar-offline sec-api-offline task005-proof task006-proof lint format-check typecheck import-check docs-check baseline-check build

review-package: setup
	$(VENV_PYTHON) scripts/generate_task006_review.py
