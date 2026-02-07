PYTHON ?= python3.14

.PHONY: setup setup-sdl3 run test lint format

setup:
	$(PYTHON) -m pip install -e .[dev]

setup-sdl3:
	$(PYTHON) -m pip install -e .[dev,sdl3]

run:
	PYTHONPATH=src $(PYTHON) -m flow_game

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff check --fix .
