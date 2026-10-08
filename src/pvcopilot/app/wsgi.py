"""WSGI entry point:  gunicorn --workers 1 --threads 8 pvcopilot.app.wsgi:server

AI starts switched off, as with `pvcopilot ui`; use the switch in the page."""
from pvcopilot.app import create_app
from pvcopilot.config import set_ai

set_ai(False)
server = create_app().server
