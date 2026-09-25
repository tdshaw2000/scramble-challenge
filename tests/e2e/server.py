"""Runs the real app (sockets included) for browser tests, in its own process.

Uses a throwaway SQLite file, the fake TNoodle and a fake clock. Adds test-only
endpoints under /__test__/ so tests can move the clock and run the abandoned-
challenge check. None of this is part of the app itself.
"""

import argparse

from flask import Blueprint, jsonify, request

from app import create_app, sockets
from app.extensions import socketio
from tests.fakes import FakeClock, FakeTNoodle

control = Blueprint("test_control", __name__, url_prefix="/__test__")


@control.post("/advance-clock")
def advance_clock():
    control.app.extensions["clock"].advance(seconds=float(request.args["seconds"]))
    return jsonify(ok=True)


@control.post("/next-scramble")
def next_scramble():
    tnoodle = control.app.extensions["tnoodle"]
    tnoodle.next_text = request.args["text"]
    width, height = request.args["width"], request.args["height"]
    tnoodle.next_svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}px" height="{height}px"><rect width="100%" height="100%"/></svg>'
    )
    return jsonify(ok=True)


@control.post("/end-abandoned")
def end_abandoned():
    sockets.end_abandoned_challenges()
    return jsonify(ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()

    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{args.database}")
    app.extensions["tnoodle"] = FakeTNoodle()
    app.extensions["clock"] = FakeClock()
    control.app = app
    app.register_blueprint(control)
    with app.app_context():
        from app.extensions import db

        db.create_all()
    socketio.run(app, host="127.0.0.1", port=args.port, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
