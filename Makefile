VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

# mcp requires Python >=3.10; prefer newest available, auto-install 3.12 via brew if needed
PYTHON  := $(shell which python3.13 python3.12 python3.11 python3.10 2>/dev/null | head -1)

.DEFAULT_GOAL := help

# ── python ────────────────────────────────────────────────────────────────────

.PHONY: python-install
python-install:  ## Install Python 3.12 via Homebrew (required if only 3.9 is present)
	brew install python@3.12
	@echo "✓ Python 3.12 installed — re-run 'make install'"

.PHONY: node-install
node-install:  ## Install Node.js via Homebrew (required for 'make inspect')
	brew install node
	@echo "✓ Node.js installed — re-run 'make inspect'"

# ── venv / install ────────────────────────────────────────────────────────────

$(VENV)/bin/activate:
	@if [ -z "$(PYTHON)" ]; then \
		echo ""; \
		echo "ERROR: Python 3.10+ is required but not found."; \
		echo "       Run:  make python-install"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Using $$($(PYTHON) --version) at $(PYTHON)"
	$(PYTHON) -m venv $(VENV)

.PHONY: venv
venv: $(VENV)/bin/activate  ## Create .venv using Python 3.10+

.PHONY: install
install: venv  ## Install mcp[cli] + httpx into the venv
	$(PIP) install --upgrade pip --quiet
	$(PIP) install "mcp[cli]" httpx "redis[asyncio]"
	@echo "✓ Dependencies installed"

# ── run ───────────────────────────────────────────────────────────────────────

.PHONY: run
run: install  ## Run with Streamable HTTP transport → http://localhost:8000/mcp
	MCP_TRANSPORT=streamable-http $(PY) src/server.py

.PHONY: run-stdio
run-stdio: install  ## Run the MCP server (stdio — for Claude Desktop)
	$(PY) src/server.py

.PHONY: run-sse
run-sse: install  ## Run with SSE transport → http://localhost:8000/sse
	MCP_TRANSPORT=sse $(PY) src/server.py

.PHONY: inspect
inspect: install  ## Launch MCP Inspector UI → http://localhost:5173  (test tools interactively)
	$(VENV)/bin/mcp dev src/server.py

# ── configure ─────────────────────────────────────────────────────────────────

.PHONY: configure
configure:  ## Create .env from .env.example: make configure CLIENT_ID=xxx CLIENT_SECRET=yyy
	@if [ -z "$(CLIENT_ID)" ] || [ -z "$(CLIENT_SECRET)" ]; then \
		echo "Usage: make configure CLIENT_ID=your_id CLIENT_SECRET=your_secret"; \
		exit 1; \
	fi
	@cp .env.example .env
	@sed -i '' "s/^MCP_DATA_TWELVE_DATA_CLIENT_ID=.*/MCP_DATA_TWELVE_DATA_CLIENT_ID=$(CLIENT_ID)/" .env
	@sed -i '' "s/^MCP_DATA_TWELVE_DATA_CLIENT_SECRET=.*/MCP_DATA_TWELVE_DATA_CLIENT_SECRET=$(CLIENT_SECRET)/" .env
	@chmod 600 .env
	@echo "✓ .env created"

# ── dev helpers ───────────────────────────────────────────────────────────────

.PHONY: check
check: venv  ## Syntax-check all Python files
	find src -name "*.py" | xargs $(PY) -m py_compile && echo "✓ Syntax OK"

.PHONY: deps-check
deps-check: venv  ## Show installed package versions
	$(PIP) show mcp httpx 2>/dev/null | grep -E "^(Name|Version):"

# ── clean ─────────────────────────────────────────────────────────────────────

.PHONY: clean
clean:  ## Remove .venv
	rm -rf $(VENV)
	@echo "✓ Removed $(VENV)"

# ── help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
