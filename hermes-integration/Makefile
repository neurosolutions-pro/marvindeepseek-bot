.PHONY: install run stop test logs health bot apply

ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV := $(ROOT).venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install -U pip setuptools wheel
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env
	@test -f hermes.config.yaml || cp hermes.config.example.yaml hermes.config.yaml
	$(PY) scripts/apply_config.py
	@echo "Installed hermes-agent + integration deps into $(VENV)"

apply:
	$(PY) scripts/apply_config.py

run: apply
	bash scripts/start_stack.sh

stop:
	bash scripts/stop_stack.sh

health:
	curl -sS http://127.0.0.1:$${HERMES_PORT:-8000}/health | python3 -m json.tool

bot:
	set -a; . ./.env; set +a; $(PY) bot_client.py "$(MSG)"

test: apply
	@bash scripts/start_stack.sh
	set -a; . ./.env; set +a; $(PY) test_bot_client.py
	@echo "All tests passed"

logs:
	@echo "=== hermes_gateway.log ==="; tail -n 80 logs/hermes_gateway.log 2>/dev/null || true
	@echo "=== bot_client.log ==="; tail -n 80 bot_client.log 2>/dev/null || true
	@echo "=== upstream.stdout.log ==="; tail -n 40 logs/upstream.stdout.log 2>/dev/null || true
	@echo "=== hermes.stdout.log ==="; tail -n 40 logs/hermes.stdout.log 2>/dev/null || true
