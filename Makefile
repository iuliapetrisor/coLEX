# coLEX Makefile. Targets are added as they start to work; nothing here is a placeholder.
PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: setup test
OFFLINE ?=

# Creates a project-local virtualenv and installs the dependencies (needs network once).
setup: $(VENV)/.installed

$(VENV)/.installed: requirements.txt requirements-dev.txt
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -q --upgrade pip
	$(BIN)/python -m pip install -q -r requirements-dev.txt
	git config core.hooksPath .githooks || true
	touch $@

# Always offline: tests/conftest.py blocks the network.
test: setup
	$(BIN)/python -m pytest

# Unattended run of the brief 1.5 scenario in the terminal. OFFLINE=1 replays recorded model answers.
.PHONY: demo
demo: setup
	COLEX_OFFLINE=$(OFFLINE) $(BIN)/python -m colex.demo

# Build the Company Map from the sandbox sources.
.PHONY: map
map: setup
	$(BIN)/python -m colex.map
