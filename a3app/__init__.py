import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, abort, g, redirect, request, session, url_for

from . import auth, db
from .config import find_config, load_config
from .model import build_options


def _secret_key(instance_path):
    key_file = Path(instance_path) / "secret_key"
    if not key_file.exists():
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(secrets.token_hex(32), encoding="utf-8")
    return key_file.read_text(encoding="utf-8").strip()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    data_dir = os.environ.get("A3_DATA_DIR", app.instance_path)
    app.config.update(
        DATABASE=str(Path(data_dir) / "a3.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _secret_key(data_dir)
    if "A3" not in app.config:
        app.config["A3"] = load_config(find_config(data_dir))
    app.config["A3_OPTIONS"] = build_options(app.config["A3"])

    db.init_db(app.config["DATABASE"])
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def csrf_and_login():
        if request.method == "POST":
            token = session.get("csrf")
            if not token or not secrets.compare_digest(token, request.form.get("csrf", "")):
                abort(400, "Invalid or missing CSRF token. Reload the page and try again.")
        auth.load_user()
        if g.user is None and request.endpoint not in ("auth.login", "auth.setup", "static"):
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))

    @app.context_processor
    def inject_globals():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return {"csrf_token": session["csrf"], "user": g.get("user"), "has_role": auth.has_role,
                "can_signoff": auth.can_signoff, "cfg_meta": app.config["A3"]["meta"]}

    app.register_blueprint(auth.bp)
    from .routes import bp
    app.register_blueprint(bp)
    return app
