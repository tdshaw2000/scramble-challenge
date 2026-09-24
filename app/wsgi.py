"""Production entry point for gunicorn. Not imported by the tests (no background thread there)."""

from app import create_app, sockets
from app.extensions import socketio

app = create_app("production")
socketio.start_background_task(sockets.watch_for_abandoned_challenges, app)
