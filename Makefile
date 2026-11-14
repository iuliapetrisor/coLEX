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

# Re-record the model answers used by `make demo OFFLINE=1` and by the offline end-to-end test.
# Calls OpenRouter for anything not in the local cache (var/llm_cache). Run it after changing a prompt.
.PHONY: record
record: setup
	rm -f tests/fixtures/llm/*.json
	COLEX_LLM_MODE=record $(BIN)/python -m colex.demo --quiet

# Console + engine (+ real Slack when SLACK_BOT_TOKEN and SLACK_APP_TOKEN are in .env; SLACK=0 turns it off).
# Serves the state of the last `make demo` (var/demo). Listens on 127.0.0.1 only: the Console has no login.
PORT ?= 8000
SLACK ?= 1
.PHONY: console reset
console: setup
	COLEX_VAR=var/demo COLEX_PORT=$(PORT) COLEX_SLACK=$(SLACK) COLEX_OFFLINE=$(OFFLINE) $(BIN)/python -m colex.server

# Delete the demo state (runs, map, sandbox repository copy). Keeps the model answer cache.
reset:
	rm -rf var/demo

# Read-only check of the real Slack workspace: auth, Socket Mode, channels. Posts nothing.
.PHONY: slack-check
slack-check: setup
	$(BIN)/python tools/slack_check.py
