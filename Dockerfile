# Use official Python 3.13 runtime
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install pip and UV for dependency management
RUN pip install --upgrade pip uv

# Copy project metadata and README for build context
COPY pyproject.toml uv.lock* README.md LICENSE ./

# Copy source code in src directory
COPY src ./src

# Install project dependencies and build the package using UV
RUN uv pip install . --system

# Run the MCP server directly from source
ENTRYPOINT ["python", "-m", "mcp_server_twelve_data"]
CMD ["-k", "demo", "-t", "streamable-http"]
