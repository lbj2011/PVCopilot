"""Command line:  pvcopilot ui | analyze | examples | config"""
from __future__ import annotations

import argparse
import json
import sys


def _llm_args(p):
    g = p.add_argument_group("LLM (optional). PV-Copilot never looks for a key on its own and "
                             "never takes the key itself; give the file and the variable name")
    g.add_argument("--env-file", help=".env file that holds your key")
    g.add_argument("--key-var", help="name of the variable in that file, e.g. CBORG_API_KEY")
    g.add_argument("--base-url", help="OpenAI-compatible endpoint, e.g. http://localhost:11434/v1")
    g.add_argument("--model", help="model name (default gpt-5.4-mini)")
    g.add_argument("--fast-model", help="model for chat / short answers")


def _apply_llm(a):
    from pvcopilot import configure
    configure(env_file=a.env_file, key_var=a.key_var, base_url=a.base_url, model=a.model,
              fast_model=a.fast_model)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pvcopilot", description="PV-Copilot, offline.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ui", help="start the local web interface")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8050)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--ai", action="store_true",
                   help="start with AI switched on (default: off; there is a switch in the page)")
    _llm_args(p)

    p = sub.add_parser("analyze", help="compute degradation rate(s) for a file")
    p.add_argument("data", help="csv / xlsx / parquet file, or a bundled example name")
    p.add_argument("-m", "--method", action="append", dest="methods",
                   help="YOY, LR, CSD, HW, ARIMA or PVPRO (repeat for several)")
    p.add_argument("--mode", choices=["simple", "advanced"])
    p.add_argument("--map", action="append", default=[], metavar="ROLE=COLUMN",
                   help='column mapping, e.g. --map "DC Power=dc_power" (skips the LLM)')
    p.add_argument("--script", help="also write the reproducible analysis script here")
    p.add_argument("--figures", help="write the figures (html) into this folder")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.add_argument("-v", "--verbose", action="store_true")
    _llm_args(p)

    p = sub.add_parser("examples", help="list the bundled example datasets")
    p.add_argument("--export", metavar="FOLDER", help="also write every example as CSV here")
    p = sub.add_parser("shortcut", help="create a double-click launcher (Desktop by default)")
    p.add_argument("--dir", help="folder for the launcher")
    p = sub.add_parser("config", help="show the LLM settings that would be used")
    p.add_argument("--forget", action="store_true",
                   help="delete the choices saved by the web UI's 'remember' option")
    _llm_args(p)

    a = ap.parse_args(argv)

    if a.cmd == "examples":
        import os
        from pvcopilot import list_examples
        from pvcopilot.examples import EXAMPLES, example_file, export_example
        t = list_examples()[["description", "location"]]
        t["path"] = [example_file(k) for k in t.index]
        print(t.to_string())
        if a.export:
            os.makedirs(a.export, exist_ok=True)
            for k in EXAMPLES:
                print("wrote", export_example(k, a.export))
        return 0
    if a.cmd == "shortcut":
        from pvcopilot.shortcut import create_shortcut
        for p in create_shortcut(a.dir):
            print("created", p)
        print("Double-click it to open PV-Copilot in your browser.")
        return 0
    if a.cmd == "config":
        from pvcopilot import config
        if a.forget:
            print("saved settings deleted" if config.clear_saved_settings()
                  else "no saved settings")
        _apply_llm(a)
        print(config.get_config().describe())
        print(f"saved-settings file: {config.settings_path()}"
              + ("" if config.settings_path().exists() else " (none)"))
        return 0
    if a.cmd == "ui":
        _apply_llm(a)
        from pvcopilot.app import run
        run(host=a.host, port=a.port, open_browser=not a.no_browser, debug=a.debug, ai=a.ai)
        return 0

    _apply_llm(a)
    from pvcopilot import analyze
    mapping = {}
    for item in a.map:
        role, _, col = item.partition("=")
        if not col:
            ap.error(f"--map needs ROLE=COLUMN, got {item!r}")
        mapping[role.strip()] = col.strip()
    methods = a.methods or ["YOY"]
    mode = a.mode or ("advanced" if len(methods) > 1 else "simple")
    try:
        res = analyze(a.data, mapping or None, methods=methods, mode=mode, verbose=a.verbose)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(res.to_dict(), indent=2, default=str) if a.json else res.summary())
    if a.script:
        res.to_script(a.script, data_file=a.data)
        print(f"script written to {a.script}")
    if a.figures:
        paths = res.save_figures(a.figures)
        print(f"{len(paths)} figures written to {a.figures}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
