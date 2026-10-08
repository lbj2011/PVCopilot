"""The Dash application object the PV-Copilot page registers its callbacks on.

Fully offline: Dash's own JS is served from the installed package, and
Bootstrap and the fonts are bundled in ``assets/``.
"""
from dash import Dash

from pvcopilot._paths import ASSETS_DIR

app = Dash(
    __name__,
    assets_folder=str(ASSETS_DIR),
    compress=False,
    update_title=None,
    suppress_callback_exceptions=True,
    title="PV-Copilot",
)
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
server = app.server
