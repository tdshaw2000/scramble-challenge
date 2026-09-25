#!/bin/sh
set -e

# Bring the SQLite schema up to date before serving.
flask db upgrade

# Worker settings live in gunicorn.conf.py.
exec gunicorn -c gunicorn.conf.py app.wsgi:app
