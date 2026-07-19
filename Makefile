PYTHON ?= python3
VENV_PYTHON := .venv/bin/python
VENV_STAMP := .venv/.rfi-installed

.PHONY: setup test focused-test acquisition-demo engine-demo edgar-offline sec-api-offline task005-proof task006-proof task007-proof task008-proof task009-proof task010-proof task011-proof task014-proof task015-proof task016-proof task017-proof task018-proof task019-proof task012-test task013-test task015-test task016-test task017-test task018-test task019-test lint format-check typecheck import-check docs-check baseline-check build validate review-package

setup: $(VENV_STAMP)

$(VENV_PYTHON):
	$(PYTHON) -m venv .venv

$(VENV_STAMP): pyproject.toml $(VENV_PYTHON)
	$(VENV_PYTHON) -m pip install -e .
	touch $(VENV_STAMP)

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

task007-proof: setup
	$(VENV_PYTHON) scripts/task007_operator.py fixture-proof

task008-proof: setup
	$(VENV_PYTHON) scripts/task008_workspace.py fixture-proof

task009-proof: setup
	$(VENV_PYTHON) scripts/task009_concepts.py fixture-proof

task010-proof: setup
	$(VENV_PYTHON) scripts/task010_admin_console.py fixture-proof

task011-proof: setup
	$(VENV_PYTHON) scripts/task011_firms.py fixture-proof

task014-proof: setup
	$(VENV_PYTHON) scripts/task014_source_profiles.py fixture-proof

task015-proof: setup
	$(VENV_PYTHON) scripts/task015_pull_workflow.py fixture-proof

task016-proof: setup
	env -u RFI_SEC_USER_AGENT $(VENV_PYTHON) scripts/task016_sec_10k.py fixture-proof

task017-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task017_admin_preferences.py

task018-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task018_artifact_browser.py

task019-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task019_artifact_observations.py

task012-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task012 -v

task013-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task013 -v

task015-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task015 -v

task016-test: setup
	env -u RFI_SEC_USER_AGENT PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task016 -v

task017-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task017 -v

task018-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task018 -v

task019-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task019 -v

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

validate: test acquisition-demo engine-demo edgar-offline sec-api-offline task005-proof task006-proof task007-proof task008-proof task009-proof task010-proof task011-proof task014-proof task015-proof task016-proof task017-proof task018-proof task019-proof lint format-check typecheck import-check docs-check baseline-check build

review-package: setup
	$(VENV_PYTHON) scripts/generate_task019_review.py
