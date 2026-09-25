from app.extensions import socketio


def test_one_players_events_are_handled_in_the_order_they_were_sent(app):
    # By default Flask-SocketIO runs every event in its own thread or greenlet, so a
    # stop_solve sent just after start_solve could be handled first and rejected. Handling
    # each connection's events one at a time keeps them in order (issue #18).
    assert socketio.server.async_handlers is False
