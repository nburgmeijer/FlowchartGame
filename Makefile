PYTHON ?= python3.14

.PHONY: setup setup-sdl2 run test lint format

setup:
	$(PYTHON) -m pip install -e .[dev]

setup-sdl2:
	$(PYTHON) -m pip install -e .[dev,sdl2]

run:
	PYTHONPATH=src $(PYTHON) -m flow_game

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff check --fix .
