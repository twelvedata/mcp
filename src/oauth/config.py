"""OAuth Authorization Server configuration, derived from the environment.

The MCP server acts as its own OAuth 2.1 Authorization Server (RFC 8414 +
RFC 7591 Dynamic Client Registration) and delegates the actual user login to
Twelve Data's OAuth (the upstream IdP). Remote MCP clients (ChatGPT, Claude
Desktop / claude.ai connectors, Cursor, …) all speak this flow uniformly.

Enable by setting MCP_DATA_PUBLIC_URL to the externally reachable base URL, e.g.
    MCP_DATA_PUBLIC_URL=https://mcp-data.twelvedata.com
"""

from __future__ import annotations

import os

# Public base URL of this server (no trailing slash). Empty => OAuth disabled
# (e.g. stdio / Claude Desktop local, which authenticates via the oauth_login tool).
PUBLIC_URL = os.environ.get("MCP_DATA_PUBLIC_URL", "").rstrip("/")

# Master switch — on by default whenever a public URL is configured.
ENABLED = bool(PUBLIC_URL) and os.environ.get("MCP_OAUTH_ENABLED", "1") not in ("0", "false", "no")

# Single scope representing "access Twelve Data on the user's behalf".
SCOPE = "twelvedata"

# Lifetimes (seconds).
CODE_TTL    = 300                                                  # authorization code
ACCESS_TTL  = int(os.environ.get("MCP_OAUTH_ACCESS_TTL",  "3600"))        # 1 hour
REFRESH_TTL = int(os.environ.get("MCP_OAUTH_REFRESH_TTL", str(30 * 24 * 3600)))  # 30 days

# Where Twelve Data redirects back to us after the upstream login. We reuse the
# already-registered "/callback" path (shared with the legacy oauth_login tool
# flow, dispatched by state), so no new redirect URI has to be registered on the
# Twelve Data OAuth app. This URL must be among the app's allowed redirect URIs.
TD_CALLBACK_PATH = "/callback"


def td_callback_url() -> str:
    return f"{PUBLIC_URL}{TD_CALLBACK_PATH}"


def issuer_url() -> str:
    return PUBLIC_URL


def resource_url() -> str:
    """Canonical resource identifier = the MCP endpoint clients POST to."""
    return f"{PUBLIC_URL}/mcp"
