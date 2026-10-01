VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

# mcp requires Python >=3.10; prefer newest available, auto-install 3.12 via brew if needed.
#
# Each candidate is PROBED and not merely located. `which a b c` prints in argument order, so
# the newest name wins wherever several are installed — and an interpreter packaged without
# ensurepip is then chosen and fails at `python -m venv`, long after this variable said it was
# fine.
PYTHON  := $(shell for p in python3.13 python3.12 python3.11 python3.10; do \
	  q=$$(command -v $$p 2>/dev/null) || continue; \
	  "$$q" -c 'import ensurepip' >/dev/null 2>&1 && echo "$$q" && break; \
	done)

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
		echo "ERROR: no Python 3.10+ that can create a virtualenv was found."; \
		echo "       Run:  make python-install"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Using $$($(PYTHON) --version) at $(PYTHON)"
	$(PYTHON) -m venv $(VENV)

.PHONY: venv
venv: $(VENV)/bin/activate  ## Create .venv using Python 3.10+

.PHONY: install
install: venv  ## Install the runtime dependencies into the venv
# The two version pins are the same ones pyproject.toml carries, and both sites matter: a
# fresh .venv resolves from this line alone. Below mcp 1.30 the SDK silently drops
# validate_token_resource and checks no audience; Starlette is pinned because hosted-mode
# code imports a function from one of its private modules.
	$(PIP) install --upgrade pip --quiet
	$(PIP) install "mcp[cli]==1.30.0" "starlette==1.6.0" httpx
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
# Copy and substitute in one pass, with no `sed -i`: its in-place spelling differs between
# GNU and BSD sed, and the BSD form this carried reads its own script as a filename on Linux
# — which left `.env` created and both credentials empty.
	@sed -e "s|^MCP_DATA_TWELVE_DATA_CLIENT_ID=.*|MCP_DATA_TWELVE_DATA_CLIENT_ID=$(CLIENT_ID)|" \
	     -e "s|^MCP_DATA_TWELVE_DATA_CLIENT_SECRET=.*|MCP_DATA_TWELVE_DATA_CLIENT_SECRET=$(CLIENT_SECRET)|" \
	     .env.example > .env
	@chmod 600 .env
	@echo "✓ .env created"

# ── dev helpers ───────────────────────────────────────────────────────────────

.PHONY: check
check: venv  ## Syntax-check all Python files
	find src -name "*.py" | xargs $(PY) -m py_compile && echo "✓ Syntax OK"

# Linting is internal tooling and lives in its own file so that this Makefile
# can be published as-is. `-include` rather than `include`: absent, it is
# silently skipped and the targets simply do not exist.
-include Makefile.lint

# Local packaging helpers (prepare-github). Absent on public checkouts — fine.
-include Makefile.local

help:  ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
