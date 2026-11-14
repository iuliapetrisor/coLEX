# coLEX Makefile. Targets are added as they start to work; nothing here is a placeholder.
PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: setup test

# Creates a project-local virtualenv and installs the dependencies (needs network once).
setup: $(VENV)/.installed

$(VENV)/.installed: requirements.txt requirements-dev.txt
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -q --upgrade pip
	$(BIN)/python -m pip install -q -r requirements-dev.txt
	touch $@

# Always offline: tests/conftest.py blocks the network.
test: setup
	$(BIN)/python -m pytest
