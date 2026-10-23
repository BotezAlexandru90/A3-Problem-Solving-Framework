import time
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .config import ROLES

bp = Blueprint("auth", __name__)

RANK = {r: i for i, r in enumerate(ROLES)}
MIN_PASSWORD = 10
_failures = {}  # username -> [timestamps]; in-memory lockout, resets on restart
LOCK_AFTER, LOCK_WINDOW = 5, 15 * 60


def has_role(min_role):
    return g.get("user") is not None and RANK[g.user["role"]] >= RANK[min_role]


def can_signoff():
    return g.get("user") is not None and g.user["role"] in current_app.config["A3"]["workflow"]["signoff_roles"]


def require(min_role):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not has_role(min_role):
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def user_name():
    return g.user["display_name"] if g.get("user") else ""


def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        u = db.get_user(uid)
        if u and u["active"]:
            g.user = u
        else:
            session.pop("uid", None)


def _locked(username):
    now = time.time()
    recent = [t for t in _failures.get(username.lower(), []) if now - t < LOCK_WINDOW]
    _failures[username.lower()] = recent
    return len(recent) >= LOCK_AFTER


def _password_error(pw, pw2):
    if len(pw) < MIN_PASSWORD:
        return f"Password must have at least {MIN_PASSWORD} characters."
    if pw != pw2:
        return "Passwords do not match."
    return None


def _login(user):
    csrf = session.get("csrf")
    session.clear()  # prevent session fixation
    session["csrf"] = csrf
    session["uid"] = user["id"]
    session.permanent = True


@bp.route("/login", methods=["GET", "POST"])
def login():
    if db.count_users() == 0:
        return redirect(url_for("auth.setup"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        if _locked(username):
            flash("Too many failed attempts. Try again in 15 minutes.", "error")
            return render_template("login.html"), 429
        u = db.get_user_by_username(username)
        if u and u["active"] and check_password_hash(u["password_hash"], pw):
            _failures.pop(username.lower(), None)
            _login(u)
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("a3.dashboard"))
        _failures.setdefault(username.lower(), []).append(time.time())
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run admin creation; only when no users exist and only from the server machine."""
    if db.count_users() > 0:
        return redirect(url_for("auth.login"))
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403, "Create the first admin on the server machine or with 'python manage.py create-user'.")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        name = request.form.get("display_name", "").strip()
        pw, pw2 = request.form.get("password", ""), request.form.get("password2", "")
        err = _password_error(pw, pw2) or (None if username and name else "Username and name are required.")
        if err:
            flash(err, "error")
        else:
            db.create_user(username, name, generate_password_hash(pw), "admin")
            _login(db.get_user_by_username(username))
            flash("Admin account created.", "ok")
            return redirect(url_for("a3.dashboard"))
    return render_template("setup.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        if not check_password_hash(g.user["password_hash"], request.form.get("current", "")):
            flash("Current password is wrong.", "error")
        else:
            pw, pw2 = request.form.get("password", ""), request.form.get("password2", "")
            err = _password_error(pw, pw2)
            if err:
                flash(err, "error")
            else:
                db.update_user(g.user["id"], password_hash=generate_password_hash(pw))
                flash("Password changed.", "ok")
                return redirect(url_for("a3.dashboard"))
    return render_template("account.html")


@bp.route("/users", methods=["GET", "POST"])
@require("admin")
def users():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = request.form.get("username", "").strip()
            name = request.form.get("display_name", "").strip()
            role = request.form.get("role", "")
            pw = request.form.get("password", "")
            err = _password_error(pw, pw) or (None if username and name else "Username and name are required.")
            if role not in ROLES:
                err = "Invalid role."
            if not err and db.get_user_by_username(username):
                err = "Username already exists."
            if err:
                flash(err, "error")
            else:
                db.create_user(username, name, generate_password_hash(pw), role)
                flash(f"User {username} created. Ask them to change the password under 'Account'.", "ok")
        elif action == "update":
            uid = int(request.form.get("user_id", 0))
            target = db.get_user(uid)
            role = request.form.get("role", "")
            active = 1 if request.form.get("active") == "1" else 0
            if target is None or role not in ROLES:
                abort(400)
            if uid == g.user["id"] and (role != "admin" or not active):
                flash("You cannot remove your own admin role or deactivate yourself.", "error")
            else:
                values = {"role": role, "active": active,
                          "display_name": request.form.get("display_name", "").strip() or target["display_name"]}
                pw = request.form.get("password", "")
                if pw:
                    err = _password_error(pw, pw)
                    if err:
                        flash(err, "error")
                        return redirect(url_for("auth.users"))
                    values["password_hash"] = generate_password_hash(pw)
                db.update_user(uid, **values)
                flash("User updated.", "ok")
        return redirect(url_for("auth.users"))
    return render_template("users.html", users=db.list_users(), roles=ROLES)
