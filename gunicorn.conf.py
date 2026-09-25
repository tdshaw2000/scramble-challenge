"""gunicorn settings for production (docker/web/entrypoint.sh). The capacity test in
tests/test_server_capacity.py starts gunicorn with this same file."""

bind = "0.0.0.0:5000"
# One worker only: live socket rooms are held in this process's memory.
workers = 1
# gevent: each open WebSocket is a cheap greenlet, not a whole thread, so one worker can
# hold thousands of players (a thread per socket froze the site at 8).
worker_class = "gevent"
