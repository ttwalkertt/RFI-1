PYTHON ?= python3
VENV_PYTHON := .venv/bin/python
VENV_STAMP := .venv/.rfi-installed

.PHONY: setup test focused-test acquisition-demo engine-demo edgar-offline sec-api-offline task005-proof task006-proof task007-proof task008-proof task009-proof task010-proof task011-proof task014-proof task015-proof task016-proof task017-proof task018-proof task019-proof task022-proof task023-proof task052-proof task053-proof task054-proof task055-proof task057-proof task058-proof task059-proof task060-proof task054-review task055-review task056-review task057-review task058-review task059-review task060-review task021-test task022-test task023-test task031-test task039-test task041-test task052-test task053-test task054-test task055-test task056-test task057-test task058-test task059-test task060-test task012-test task013-test task015-test task016-test task017-test task018-test task019-test lint format-check typecheck import-check docs-check baseline-check build validate review-package

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

task022-proof: setup
	env -u RFI_SEC_USER_AGENT PYTHONPATH=src $(VENV_PYTHON) scripts/task022_sec_forms.py fixture-proof

task023-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task023_mailing_lists.py fixture-proof

task052-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task052_transcript_hints.py

task053-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task053_traversal_budget.py

task054-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task054_reload_firm_profiles.py

task055-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task055_configuration_status.py

task057-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task057_reproduction.py

task058-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task058_orchestration.py

task059-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task059_selection.py

task060-proof: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/task060_seed_injection.py

task054-review: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/generate_task054_review.py

task055-review: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/generate_task055_review.py

task056-review: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/generate_task056_review.py

task057-review: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/generate_task057_review.py

task058-review: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/generate_task058_review.py

task059-review: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/generate_task059_review.py

task060-review: setup
	PYTHONPATH=src $(VENV_PYTHON) scripts/generate_task060_review.py

task056-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task056 -v

task057-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task057 tests.test_task056 tests.test_task053 tests.test_task052 tests.test_task048 tests.test_task048a tests.test_task015 tests.test_task016 -v

task058-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task058 tests.test_task057 tests.test_task056 tests.test_task053 tests.test_task052 tests.test_task048 tests.test_task048a tests.test_task015 tests.test_task016 -v

task059-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task059 tests.test_task058 tests.test_task057 tests.test_task056 tests.test_task053 tests.test_task052 tests.test_task048 tests.test_task048a tests.test_task015 tests.test_task016 -v

task060-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task060 tests.test_task059 tests.test_task058 tests.test_task057 tests.test_task056 tests.test_task053 tests.test_task052 tests.test_task048 tests.test_task048a tests.test_task015 tests.test_task016 -v

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

task021-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task021 -v

task022-test: setup
	env -u RFI_SEC_USER_AGENT PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task022 -v

task023-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task023 -v

task031-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task031 -v

task039-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task039 -v

task041-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task041 -v

task052-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task052 tests.test_task048a tests.test_task015 -v

task053-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task053 tests.test_task052 tests.test_task048a tests.test_task015 tests.test_task016 -v

task054-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task054 tests.test_task041 tests.test_task044 tests.test_task015 tests.test_task016 tests.test_task052 tests.test_task053 -v

task055-test: setup
	PYTHONPATH=src $(VENV_PYTHON) -m unittest tests.test_task055 tests.test_task054 tests.test_task041 tests.test_task044 tests.test_task015 tests.test_task016 tests.test_task021 tests.test_task052 tests.test_task053 -v

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

validate: test acquisition-demo engine-demo edgar-offline sec-api-offline task005-proof task006-proof task007-proof task008-proof task009-proof task010-proof task011-proof task014-proof task015-proof task016-proof task017-proof task018-proof task019-proof task022-proof task023-proof lint format-check typecheck import-check docs-check baseline-check build

review-package: setup
	$(VENV_PYTHON) scripts/generate_task050_review.py
