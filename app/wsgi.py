"""Production entry point for gunicorn. Tests only run it in a subprocess (test_server_capacity)."""

from app import create_app, services, sockets
from app.extensions import socketio

app = create_app("production")
with app.app_context():
    services.reset_presence_after_restart()
socketio.start_background_task(sockets.watch_for_abandoned_challenges, app)
