"""Local PV-Copilot web interface (the same Dash page as pvtools.lbl.gov/pv-copilot)."""
from __future__ import annotations

import os
import threading
import webbrowser

# Keep the PVPRO job store and session cache in the user cache dir.
from pvcopilot._paths import user_cache_dir as _ucd

os.environ.setdefault("PVC_SESSION_CACHE_DIR", os.path.join(_ucd(), "session"))


def create_app():
    """Build the Dash app with the PV-Copilot page as its layout."""
    from dash import html
    from pvcopilot import __version__
    from pvcopilot.app._dash import app
    from pvcopilot.app import page   # registers every callback on `app`

    footer = html.Div(
        style={"textAlign": "center", "color": "#64748b", "fontSize": "12px",
               "padding": "24px 0 32px"},
        children=[
            html.P(f"PV-Copilot {__version__} · running locally · "
                   "Lawrence Berkeley National Laboratory / DuraMAT"),
            html.P("Funding provided by U.S. DOE Office of Critical Minerals and Energy "
                   "Innovation (CMEI) Solar Energy Technologies Office (SETO) and as part of "
                   "the Durable Module Materials Consortium 2 (DuraMAT 2)."),
        ])
    from pvcopilot.app import local_shell
    app.layout = html.Div([local_shell.top_bar(), local_shell.settings_panel(),
                           page.layout, footer])
    if not getattr(app, "_pvc_local_registered", False):
        local_shell.register(app)
        app._pvc_local_registered = True
    return app


def run(host="127.0.0.1", port=8050, open_browser=True, debug=False, ai=False):
    """Start the local server (blocking). Ctrl+C to stop.

    AI starts switched OFF (no LLM calls) unless ai=True; the switch in the
    page's top bar turns it on or off at any time."""
    from pvcopilot import llm
    from pvcopilot.config import get_config, set_ai
    set_ai(ai)

    import logging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)   # no per-request lines

    # Double-clicking the launcher again: reuse the running copy instead of failing.
    state = _port_state(host, port)
    if state == "pvcopilot":
        url = f"http://{host}:{port}/"
        print("PV-Copilot is already running ->", url)
        if open_browser:
            webbrowser.open(url)
        return
    if state == "busy":
        port = _free_port(host, port + 1)

    app = create_app()
    url = f"http://{host}:{port}/"
    cfg = get_config()
    print("PV-Copilot (local)  ->", url)
    print(cfg.describe())
    if not cfg.ai_on:
        print("AI is switched OFF: no LLM calls. Use the AI switch in the page's top bar.")
    elif not llm.is_configured():
        print("note: no API key provided - columns are matched by name. Give the .env file and\n"
              "      the key variable in the page's AI settings, or --env-file / --key-var.")
    if cfg.enabled and not any(h in (cfg.base_url or "") for h in ("localhost", "127.0.0.1")):
        print(f"AI is on: column names and, for AI diagnosis / chat, data summaries are sent to "
              f"{cfg.base_url or 'OpenAI'}.")
    else:
        print("Nothing leaves this computer (AI is off or uses a local model).")
    print("Close this window (or press Ctrl+C) to stop.")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)


def _port_state(host, port):
    """'free', 'pvcopilot' (our server already runs there) or 'busy' (something else)."""
    import socket
    import urllib.request
    with socket.socket() as sk:
        sk.settimeout(0.5)
        if sk.connect_ex((host, port)) != 0:
            return "free"
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=2) as r:
            return "pvcopilot" if b"PV-Copilot" in r.read(4000) else "busy"
    except Exception:
        return "busy"


def _free_port(host, start):
    import socket
    for p in range(start, start + 50):
        with socket.socket() as sk:
            if sk.connect_ex((host, p)) != 0:
                return p
    raise RuntimeError("no free port found")
