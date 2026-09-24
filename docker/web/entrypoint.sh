#!/bin/sh
set -e

# Bring the SQLite schema up to date before serving.
flask db upgrade

# One worker only: live socket rooms are held in this process's memory.
exec gunicorn --workers 1 --threads 8 --bind 0.0.0.0:5000 app.wsgi:app
