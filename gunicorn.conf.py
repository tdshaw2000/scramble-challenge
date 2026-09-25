"""gunicorn settings for production (docker/web/entrypoint.sh). The capacity test in
tests/test_server_capacity.py starts gunicorn with this same file."""

bind = "0.0.0.0:5000"
# One worker only: live socket rooms are held in this process's memory.
workers = 1
worker_class = "gthread"
threads = 8
