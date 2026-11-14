.PHONY: help install test lint format clean collect-daily collect-monthly

VENV = .venv
PYTHON = $(VENV)/bin/python
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff

help:
	@echo "CloudCost Pilot - Automation Targets"
	@echo "  make install         Install runtime and dev dependencies in .venv"
	@echo "  make test            Run automated test suite"
	@echo "  make lint            Run Ruff linter"
	@echo "  make format          Run Ruff formatter"
	@echo "  make collect-daily   Run daily Cost Explorer collection"
	@echo "  make collect-monthly Run monthly Cost Explorer collection"
	@echo "  make clean           Clean caches and temp artifacts"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTEST) -v --cov=app --cov-report=term-missing

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete

collect-daily:
	$(PYTHON) scripts/collect_costs.py --granularity DAILY

collect-monthly:
	$(PYTHON) scripts/collect_costs.py --granularity MONTHLY
