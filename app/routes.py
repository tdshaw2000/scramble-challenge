from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import db

bp = Blueprint("main", __name__)


@bp.get("/healthz")
def health():
    db.session.execute(text("SELECT 1"))
    return jsonify(status="ok")
