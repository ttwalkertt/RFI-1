PYTHON ?= python3
VENV_PYTHON := .venv/bin/python

.PHONY: setup test lint format-check typecheck import-check docs-check baseline-check build validate review-package

setup:
	$(PYTHON) -m venv .venv

test: setup
	$(VENV_PYTHON) -m unittest discover -s tests -v

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

validate: test lint format-check typecheck import-check docs-check baseline-check build

review-package: setup
	$(VENV_PYTHON) scripts/generate_review_package.py
