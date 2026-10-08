"""The local-version frame around the PV-Copilot page.

* a top bar that says plainly this is the offline / local version and what
  does and does not leave the computer;
* an "AI settings" panel. It does NOT accept a typed API key: the user picks
  the .env file and the name of the variable that holds the key (plus endpoint
  and model). The key is read from that file on this computer, kept in memory,
  never shown in full, never sent to the browser and never written to disk.

The page itself (page.py) is the website's page, unchanged apart from the
packaging edits; everything local-only lives here.
"""
from __future__ import annotations

import os

import dash
from dash import Input, Output, State, dcc, html

from pvcopilot import config, llm

_P = "pvc-local-"          # id prefix, so nothing collides with the page's ids

# (short text in the bar, full sentence on hover)
BAR_AI_OFF = ("Nothing leaves this computer.",
              "Runs on this computer (127.0.0.1). AI is off: no data, no key, nothing is sent.")
BAR_AI_LOCAL = ("Nothing leaves this computer.",
                "Runs on this computer (127.0.0.1). AI uses a model on this computer.")
BAR_AI_REMOTE = ("Data summaries are sent to {where} ⓘ",
                 "The data file is not uploaded. With AI on, these are sent to {where}: column "
                 "names (Run analysis), file name / time range / rates / monthly averages "
                 "(AI diagnosis), your questions + analysis summary (chat), the script "
                 "(Generate code). See AI settings › What is sent.")

WHAT_IS_SENT = [
    html.Li([html.B("Without AI (no key): "), "nothing leaves this computer. Columns are "
             "matched by name."]),
    html.Li([html.B("With a model on this computer "), "(Ollama, LM Studio, vLLM at "
             "localhost): nothing leaves this computer either."]),
    html.Li([html.B("With a remote AI service "), "(OpenAI, CBorg, …), the file is never "
             "uploaded as such, but these texts are sent to it:",
             html.Ul([
                 html.Li([html.B("Run analysis"), " (automatic): the column names."]),
                 html.Li([html.B("AI diagnosis"), " (button): file name, time range, row "
                          "counts, filter results, degradation rates, data gaps and "
                          "monthly averages of power, irradiance, temperature, V and I."]),
                 html.Li([html.B("Ask PVCopilot"), " (chat): your questions and a summary of "
                          "the current analysis."]),
                 html.Li([html.B("Generate code with AI"), ": the analysis script "
                          "(settings and column names, no measurements)."]),
             ])]),
    html.Li([html.B("Your API key: "), "never typed in here. It is read from the .env file / "
             "variable you choose below, kept in memory, and used only for that service."]),
]


def _status():
    c = config.get_config()
    found = (f"Key {config.mask(c.api_key)} found ({c.source})." if c.api_key else
             (f"{c.key_var} is empty in {c.env_file}." if c.env_file else
              "No key provided yet: choose your .env file and the key variable below."))
    if not c.ai_on:
        return ("", "off", BAR_AI_OFF,
                "AI is switched off: no LLM calls. " + found)
    if not c.enabled:
        return ("AI on · no key", "off", BAR_AI_OFF,
                found + " Columns are matched by name; AI diagnosis, chat and code tidy-up "
                        "need a key or a local model.")
    where = c.base_url or "api.openai.com"
    local = any(h in where for h in ("localhost", "127.0.0.1", "0.0.0.0"))
    key = f"key {config.mask(c.api_key)} from {c.source}" if c.api_key else "no key (local)"
    return (f"AI · {c.resolved_model}" + (" · local" if local else ""),
            "local" if local else "on",
            BAR_AI_LOCAL if local else tuple(t.format(where=c.base_url or "OpenAI")
                                             for t in BAR_AI_REMOTE),
            f"Endpoint: {c.base_url or 'https://api.openai.com/v1'} · model: "
            f"{c.resolved_model} · {key}")


def top_bar():
    return html.Div(className="pvcl-bar", children=[
        html.Div(className="pvcl-bar-left", children=[
            html.Span([html.Span(className="pvcl-dot"),
                       html.Span("LOCAL · OFFLINE", id=_P + "badgetext")],
                      id=_P + "badge", className="pvcl-badge"),
            html.Span(id=_P + "bartext", className="pvcl-bar-text"),
        ]),
        html.Div(className="pvcl-bar-right", children=[
            html.Button([html.Span(className="pvcl-knob"), html.Span("AI", className="pvcl-sw-label")],
                        id=_P + "aiswitch", n_clicks=0, className="pvcl-switch",
                        title="Switch all AI features on or off. Off = no LLM calls at all."),
            html.Span(id=_P + "chip", className="pvcl-chip"),
            html.Button("AI settings", id=_P + "open", n_clicks=0, className="pvcl-btn"),
        ]),
    ])


def settings_panel():
    cur = config.current_settings()
    if not any(cur.values()):
        cur = config.remembered_settings()     # prefill only; Apply makes it active
    return html.Div(id=_P + "panel", className="pvcl-panel", style={"display": "none"},
                    children=[html.Div(className="pvcl-card", children=[
        html.Div(className="pvcl-card-head", children=[
            html.H3("AI settings"),
            html.Button("×", id=_P + "close", n_clicks=0, className="pvcl-x", title="Close"),
        ]),
        html.P(["Point to the ", html.Code(".env"), " file with your key and name the "
                "variable. The key is never typed here, and never looked up on its own. "
                "Local model (Ollama)? Fill only 3 and 4."], className="pvcl-muted"),
        html.Details([html.Summary("What is sent, and when?"),
                      html.Ul(WHAT_IS_SENT, className="pvcl-list")], className="pvcl-details"),
        html.Div(id=_P + "current", className="pvcl-current"),

        html.Label(["1 · .env file ", _tip("Path of the .env file that holds your key, e.g. "
                                         "~/keys/pvcopilot.env. Required: PV-Copilot never "
                                         "looks for keys on its own.")],
                   htmlFor=_P + "envfile"),
        html.Div(className="pvcl-row", children=[
            dcc.Input(id=_P + "envfile", type="text", value=cur.get("env_file") or "",
                      placeholder="~/pvtools/.env",
                      className="pvcl-input"),
            html.Button("Check file", id=_P + "scan", n_clicks=0, className="pvcl-btn"),
        ]),
        html.Div(id=_P + "scanmsg", className="pvcl-hint"),

        html.Label(["2 · Key variable ", _tip("Name of the variable in that file that holds the "
                                            "key. Click Check file to list the names; values are "
                                            "never shown.")],
                   htmlFor=_P + "keyvar"),
        dcc.Dropdown(id=_P + "keyvar", value=cur.get("key_var"), clearable=True,
                     searchable=True,
                     options=([{"label": cur["key_var"], "value": cur["key_var"]}]
                              if cur.get("key_var") else []),
                     placeholder="click “Check file” first",
                     className="pvcl-dd"),

        html.Label(["3 · Endpoint ", _tip("Which AI service to call. Empty: OpenAI. CBorg: "
                                        "https://api.cborg.lbl.gov. A model on this computer "
                                        "(Ollama): http://localhost:11434/v1")],
                   htmlFor=_P + "url"),
        dcc.Input(id=_P + "url", type="text", value=cur.get("base_url") or "",
                  placeholder="empty = OpenAI",
                  className="pvcl-input"),
        html.Label(["4 · Model ", _tip("Model name as your provider spells it, e.g. "
                                     "openai/gpt-5.4-mini on CBorg, qwen3:14b on Ollama. "
                                     f"Empty: {config.DEFAULT_MODEL}.")],
                   htmlFor=_P + "model"),
        dcc.Input(id=_P + "model", type="text", value=cur.get("model") or "",
                  placeholder=f"empty = {config.DEFAULT_MODEL}", className="pvcl-input"),
        dcc.Checklist(id=_P + "remember",
                      options=[{"label": " Remember (never the key)", "value": "yes"}],
                      value=[], className="pvcl-check"),
        html.Div(className="pvcl-actions", children=[
            html.Button("Apply", id=_P + "save", n_clicks=0, className="pvcl-btn pvcl-primary"),
            html.Button("Test connection", id=_P + "test", n_clicks=0, className="pvcl-btn"),
            html.Button("Reset", id=_P + "clear", n_clicks=0, className="pvcl-btn pvcl-ghost"),
        ]),
        dcc.Loading(html.Div(id=_P + "msg", className="pvcl-msg"), type="dot"),
    ])])


def _tip(text):
    return html.Span("ⓘ", title=text, className="pvcl-tip")


def _scan(path):
    """Names of the variables in a .env file (key-like ones first)."""
    p = os.path.expanduser(os.path.expandvars((path or "").strip().strip("\"'“”")))
    if not p:
        return [], html.Span("Enter the path of your .env file.", className="pvcl-bad")
    if not os.path.isfile(p):
        return [], html.Span(f"File not found: {p}", className="pvcl-bad")
    names = config.env_file_variables(p)
    if not names:
        return [], html.Span(f"{p} has no variables.", className="pvcl-bad")
    names.sort(key=lambda t: (not t[1], t[0]))
    keyish = [n for n, k in names if k]
    return [n for n, _ in names], html.Span(
        f"✓ {len(names)} variable{'s' if len(names) != 1 else ''}" + (f" · key-like: {', '.join(keyish)}" if keyish else ""),
        className="pvcl-good", title=p)


def register(app):
    @app.callback(
        Output(_P + "panel", "style"),
        Input(_P + "open", "n_clicks"), Input(_P + "close", "n_clicks"),
        Input(_P + "aiswitch", "n_clicks"),
        prevent_initial_call=True,
    )
    def _toggle(_o, _c, _s):
        trig = dash.callback_context.triggered_id
        if trig == _P + "aiswitch":
            # switching on with nothing to call: show where to set it up
            if not config.ai_is_on() and not config.get_config().has_credentials:
                return {"display": "flex"}
            return dash.no_update
        return {"display": "flex"} if trig == _P + "open" else {"display": "none"}

    @app.callback(
        Output(_P + "keyvar", "options"), Output(_P + "scanmsg", "children"),
        Input(_P + "scan", "n_clicks"), Input(_P + "open", "n_clicks"),
        State(_P + "envfile", "value"), State(_P + "keyvar", "value"),
        prevent_initial_call=True,
    )
    def _scan_cb(_n, _o, path, current):
        names, msg = _scan(path)
        if dash.callback_context.triggered_id == _P + "open" and not (path or "").strip():
            msg = ""
        if current and current not in names:
            names = [current] + names
        return [{"label": n, "value": n} for n in names], msg

    @app.callback(
        Output(_P + "chip", "children"), Output(_P + "chip", "className"),
        Output(_P + "bartext", "children"), Output(_P + "bartext", "title"),
        Output(_P + "aiswitch", "className"),
        Output(_P + "badgetext", "children"), Output(_P + "badge", "className"),
        Output(_P + "current", "children"), Output(_P + "msg", "children"),
        Input(_P + "save", "n_clicks"), Input(_P + "clear", "n_clicks"),
        Input(_P + "test", "n_clicks"), Input(_P + "aiswitch", "n_clicks"),
        State(_P + "envfile", "value"), State(_P + "keyvar", "value"),
        State(_P + "url", "value"), State(_P + "model", "value"),
        State(_P + "remember", "value"),
    )
    def _settings(_s, _c, _t, _sw, envfile, keyvar, url, model, remember):
        trig = dash.callback_context.triggered_id
        msg = ""
        if trig == _P + "aiswitch":
            config.set_ai(not config.ai_is_on())
        envfile, keyvar, url, model = ((v or "").strip() for v in (envfile, keyvar, url, model))
        try:
            if trig in (_P + "save", _P + "test"):
                config.reset()
                config.configure(env_file=envfile or None, key_var=keyvar or None,
                                 base_url=url or None, model=model or None)
                if trig == _P + "save":
                    msg = "Applied for this session."
                    if remember:
                        p = config.save_settings(**config.current_settings())
                        msg = f"Applied and remembered in {p} (no key stored)."
                else:
                    msg = _test()
            elif trig == _P + "clear":
                config.reset()
                removed = config.clear_saved_settings()
                msg = "Back to the defaults" + (", remembered choices deleted." if removed
                                                else ".")
        except (FileNotFoundError, ValueError, KeyError) as e:
            msg = html.Span(str(e.args[0] if e.args else e), className="pvcl-bad")
        label, kind, bar, detail = _status()
        online = kind == "on"
        return (label, f"pvcl-chip pvcl-{kind}", bar[0], bar[1],
                "pvcl-switch pvcl-switch-on" if config.ai_is_on() else "pvcl-switch",
                "LOCAL · AI ONLINE" if online else "LOCAL · OFFLINE",
                "pvcl-badge pvcl-badge-online" if online else "pvcl-badge", detail, msg)


def _test():
    c = config.get_config()
    if not c.enabled:
        return html.Span("Nothing to call yet: give the .env file and key variable (or an "
                         "endpoint for a local model).",
                         className="pvcl-bad")
    try:
        cli = llm.get_client().with_options(timeout=30)
        r = cli.chat.completions.create(
            model=llm.get_model(),
            messages=[{"role": "user", "content": "Reply with the single word OK."}])
        text = (r.choices[0].message.content or "").strip()[:40]
        return html.Span(f"Connected · {llm.get_model()} replied “{text}”.",
                         className="pvcl-good")
    except Exception as e:  # the provider's reason (wrong key, unknown model, ...)
        return html.Span(f"Connection failed: {llm.describe_error(e)}. "
                         f"({type(e).__name__}: {llm.redact(e)[:200]})", className="pvcl-bad")
