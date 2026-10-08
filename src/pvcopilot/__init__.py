"""PV-Copilot — LLM-assisted PV degradation analysis, offline.

Two ways to use it:

* Python:   ``pvcopilot.analyze(data, ...)`` returns the degradation rate(s),
            figures and a reproducible script, no browser involved.
* Web UI:   ``pvcopilot ui`` (or ``pvcopilot.run_app()``) starts the same
            interface as pvtools.lbl.gov/pv-copilot on your own machine.

The LLM (column identification, AI diagnosis, chat) uses YOUR key, read from your
environment or a .env file (never typed in), and any OpenAI-compatible endpoint —
see :func:`configure`.
"""
__version__ = "0.1.0"

import warnings as _w

# rdtools 2.1.8 imports pkg_resources; the deprecation notice is noise for users.
_w.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)



def _guard_xgboost():
    """rdtools imports xgboost at import time, only for a clipping filter PV-Copilot
    does not use. On macOS the xgboost wheel needs the OpenMP runtime (libomp);
    without it the import fails and would take PV-Copilot down with it. Put a stub
    in its place so everything else works."""
    import sys
    import types
    try:
        import xgboost  # noqa: F401
    except Exception as e:  # ImportError, or XGBoostError when libomp is missing
        stub = types.ModuleType("xgboost")
        reason = f"{type(e).__name__}: {e}"

        class XGBClassifier:                       # noqa: D401
            def __init__(self, *a, **k):
                raise ImportError("xgboost is not usable here (" + reason + "). On macOS: "
                                  "brew install libomp. PV-Copilot itself does not need it.")
        stub.XGBClassifier = XGBClassifier
        stub.__pvcopilot_stub__ = True
        sys.modules["xgboost"] = stub


_guard_xgboost()

from .config import configure, get_config, set_ai
from .examples import EXAMPLE_MAPPINGS, export_example, list_examples, load_example
from .pipeline import Result, analyze, identify_columns, read_data

__all__ = ["analyze", "Result", "configure", "get_config", "set_ai", "list_examples", "load_example",
           "export_example", "EXAMPLE_MAPPINGS",
           "identify_columns", "read_data", "run_app", "__version__"]


def run_app(host="127.0.0.1", port=8050, open_browser=True, env_file=None, key_var=None,
            base_url=None, model=None, debug=False, ai=False):
    """Start the local web interface (blocking)."""
    if env_file or key_var or base_url or model:
        configure(env_file=env_file, key_var=key_var, base_url=base_url, model=model)
    from .app import run
    run(host=host, port=port, open_browser=open_browser, debug=debug, ai=ai)
