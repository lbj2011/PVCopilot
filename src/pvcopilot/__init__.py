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
