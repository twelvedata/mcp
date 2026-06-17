"""HTML views for OAuth callback pages."""

from starlette.responses import HTMLResponse


def callback_page(
    heading: str,
    body: str,
    kind: str = "success",  # "success" | "error"
    status: int = 200,
) -> HTMLResponse:
    """Render a styled OAuth callback page matching the Twelve Data design language."""
    if kind == "success":
        icon = (
            '<svg width="28" height="28" viewBox="0 0 24 24" fill="none"'
            ' stroke="var(--state-fg)" stroke-width="2.5"'
            ' stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="20 6 9 17 4 12"/></svg>'
        )
    else:
        icon = (
            '<svg width="28" height="28" viewBox="0 0 24 24" fill="none"'
            ' stroke="var(--state-fg)" stroke-width="2.5"'
            ' stroke-linecap="round" stroke-linejoin="round">'
            '<line x1="18" y1="6" x2="6" y2="18"/>'
            '<line x1="6" y1="6" x2="18" y2="18"/></svg>'
        )

    state_light = "#f0fdf4, #bbf7d0, #16a34a" if kind == "success" else "#fef2f2, #fecaca, #dc2626"
    state_dark  = "#052e16, #166534, #4ade80" if kind == "success" else "#2d0a0a, #7f1d1d, #f87171"
    sl_bg, sl_border, sl_fg = state_light.split(", ")
    sd_bg, sd_border, sd_fg = state_dark.split(", ")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="/favicon.png" type="image/png">
  <title>{heading} — Twelve Data</title>
  <style>
    :root {{
      --bg:           #f0f4ff;
      --surface:      #ffffff;
      --border:       #dde3f0;
      --text:         #0f1729;
      --text-muted:   #5a6a8a;
      --accent:       #1d4ed8;
      --state-bg:     {sl_bg};
      --state-border: {sl_border};
      --state-fg:     {sl_fg};
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg:           #0c111d;
        --surface:      #131b2e;
        --border:       #1e2d4e;
        --text:         #e2e8f0;
        --text-muted:   #7a8aaa;
        --accent:       #3b82f6;
        --state-bg:     {sd_bg};
        --state-border: {sd_border};
        --state-fg:     {sd_fg};
      }}
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 2.5rem 2rem;
      width: 100%;
      max-width: 400px;
      text-align: center;
      box-shadow: 0 4px 24px rgba(0,0,0,.06);
    }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: .5rem;
      font-size: .9375rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 2rem;
    }}
    .state-icon {{
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: var(--state-bg);
      border: 1px solid var(--state-border);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 1.5rem;
    }}
    h1 {{
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -.015em;
      margin-bottom: .5rem;
    }}
    .subtitle {{
      font-size: .9375rem;
      color: var(--text-muted);
      line-height: 1.55;
      margin-bottom: 1.5rem;
    }}
    .token {{
      display: inline-flex;
      align-items: center;
      gap: .375rem;
      background: var(--state-bg);
      border: 1px solid var(--state-border);
      border-radius: 8px;
      padding: .375rem .875rem;
      font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
      font-size: .8125rem;
      color: var(--state-fg);
      margin-bottom: 1.75rem;
    }}
    hr {{
      border: none;
      border-top: 1px solid var(--border);
      margin-bottom: 1.25rem;
    }}
    .hint {{
      font-size: .875rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
           stroke="var(--accent)" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
      Twelve Data
    </div>

    <div class="state-icon">{icon}</div>

    <h1>{heading}</h1>
    {body}

    <hr>
    <p class="hint">You can close this tab and return to your AI assistant.</p>
  </div>
</body>
</html>"""
    return HTMLResponse(html, status_code=status)
