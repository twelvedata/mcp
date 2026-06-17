FROM python:3.12-slim

WORKDIR /app

# Install deps from pyproject.toml (single source of truth — no drift). Only
# pyproject is copied first so this layer stays cached on code-only changes.
# We install just the dependency list (not the project itself); the app runs
# from the copied src/ below via `python server.py`.
COPY pyproject.toml .
RUN python -c "import tomllib, subprocess; deps = tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; subprocess.check_call(['pip','install','--no-cache-dir',*deps])"

COPY src/ ./

ENV MCP_TRANSPORT=streamable-http

EXPOSE 8000

CMD ["python", "server.py"]
