import sqlite3
from datetime import datetime
from pathlib import Path

from flask import current_app, g

from .model import ACTION_TYPE_STEP, CHILD_MAIN, CHILD_STEP, EDITABLE_COLUMNS, FIELD_STEP, STEPS

CHILD_TABLES = {
    "is_is_not": ["dimension", "is_value", "is_not_value", "difference"],
    "hypothesis": ["category", "hypothesis", "fishbone", "reasoning", "verification_method", "expected_if_true",
                   "actual_result", "evidence", "status", "owner", "due_date"],
    "action": ["action_type", "description", "cause_id", "owner", "due_date", "status",
               "expected_result", "verification_evidence", "effectiveness", "completed_date"],
    "read_across": ["scope_item", "rationale", "action", "owner", "due_date", "status", "confirmation"],
    "lesson": ["title", "context", "learning", "documented_where", "distribution", "standard_updated"],
    "why_step": ["cause_id", "statement", "seq", "evidence", "status", "is_root"],
    "measurement": ["m_date", "value", "note"],
}
CHILD_ORDER = {"why_step": "cause_id, seq, id", "measurement": "m_date, id"}
NON_TEXT = {"cause_id", "seq", "value"}

# Columns added after the first release; applied to existing databases on start-up.
MIGRATIONS = [
    ("a3", "containment_evidence", "TEXT NOT NULL DEFAULT ''"),
    ("a3", "target_direction", "TEXT NOT NULL DEFAULT 'Lower is better'"),
    ("a3", "is_template", "INTEGER NOT NULL DEFAULT 0"),
    ("hypothesis", "fishbone", "TEXT NOT NULL DEFAULT ''"),
]


class ConflictError(Exception):
    """Raised when an A3 was changed by someone else since it was loaded."""


def now():
    return datetime.now().isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        # Default rollback journal (not WAL): WAL is unsafe on network shares.
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with sqlite3.connect(path) as con:
        con.executescript(schema)
        for table, col, decl in MIGRATIONS:
            if col not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


# ---------- history ----------

def _s(v):
    return None if v is None else str(v)


def _log(db, a3_id, user, step, entity, entity_id, field, old, new):
    db.execute(
        "INSERT INTO history (a3_id, ts, user, step, entity, entity_id, field, old_value, new_value) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (a3_id, now(), user, step, entity, entity_id, field, _s(old), _s(new)),
    )


def list_history(a3_id):
    return get_db().execute("SELECT * FROM history WHERE a3_id = ? ORDER BY id DESC", (a3_id,)).fetchall()


def status_history():
    return get_db().execute(
        "SELECT a3_id, ts, new_value FROM history WHERE entity = 'a3' AND field = 'status' ORDER BY a3_id, id"
    ).fetchall()


# ---------- A3 ----------

def list_a3s(templates=False):
    return get_db().execute("SELECT * FROM a3 WHERE is_template = ? ORDER BY updated_at DESC",
                            (1 if templates else 0,)).fetchall()


def get_a3(a3_id):
    return get_db().execute("SELECT * FROM a3 WHERE id = ?", (a3_id,)).fetchone()


def create_a3(title, user, copy_from=None):
    """copy_from: optional dict of editable column values to pre-fill."""
    db = get_db()
    ts = now()
    cur = db.execute(
        "INSERT INTO a3 (title, created_at, updated_at, updated_by, start_date) VALUES (?, ?, ?, ?, ?)",
        (title, ts, ts, user, ts[:10]),
    )
    a3_id = cur.lastrowid
    _log(db, a3_id, user, "general", "a3", a3_id, "(created)", None, title)
    if copy_from:
        cols = [c for c in copy_from if c in EDITABLE_COLUMNS and c != "title"]
        if cols:
            db.execute(f"UPDATE a3 SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
                       [copy_from[c] for c in cols] + [a3_id])
    db.commit()
    return a3_id


def update_a3(a3_id, version, values, user):
    cols = [c for c in values if c in EDITABLE_COLUMNS or c in ("status", "closed_date", "is_template")]
    if not cols:
        return
    db = get_db()
    old = get_a3(a3_id)
    assignments = ", ".join(f"{c} = ?" for c in cols)
    params = [values[c] for c in cols] + [now(), user, a3_id, version]
    cur = db.execute(
        f"UPDATE a3 SET {assignments}, updated_at = ?, updated_by = ?, version = version + 1 "
        "WHERE id = ? AND version = ?",
        params,
    )
    if cur.rowcount == 0:
        db.rollback()
        raise ConflictError()
    for c in cols:
        if _s(old[c]) != _s(values[c]):
            _log(db, a3_id, user, FIELD_STEP.get(c, ""), "a3", a3_id, c, old[c], values[c])
    db.commit()


def touch_a3(a3_id, user):
    get_db().execute("UPDATE a3 SET updated_at = ?, updated_by = ? WHERE id = ?", (now(), user, a3_id))


def delete_a3(a3_id, user):
    db = get_db()
    title = get_a3(a3_id)["title"]
    db.execute("DELETE FROM a3 WHERE id = ?", (a3_id,))
    _log(db, a3_id, user, "", "a3", a3_id, "(deleted)", title, None)
    db.commit()


# ---------- child tables ----------

def _child_step(table, row):
    if table == "action":
        return ACTION_TYPE_STEP.get(row["action_type"], "c")
    return CHILD_STEP.get(table, "")


def list_children(table, a3_id):
    order = CHILD_ORDER.get(table, "id")
    return get_db().execute(f"SELECT * FROM {table} WHERE a3_id = ? ORDER BY {order}", (a3_id,)).fetchall()


def get_child(table, row_id):
    return get_db().execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()


def save_child(table, a3_id, row_id, values, user):
    cols = [c for c in CHILD_TABLES[table] if c in values]
    data = [values[c] for c in cols]
    db = get_db()
    if row_id:
        old = get_child(table, row_id)
        assignments = ", ".join(f"{c} = ?" for c in cols)
        db.execute(f"UPDATE {table} SET {assignments} WHERE id = ? AND a3_id = ?", data + [row_id, a3_id])
        merged = dict(old) | values
        for c in cols:
            if _s(old[c]) != _s(values[c]):
                _log(db, a3_id, user, _child_step(table, merged), table, row_id, c, old[c], values[c])
    else:
        cur = db.execute(
            f"INSERT INTO {table} (a3_id, {', '.join(cols)}) VALUES (?, {', '.join('?' * len(cols))})",
            [a3_id] + data,
        )
        _log(db, a3_id, user, _child_step(table, values), table, cur.lastrowid, "(created)", None,
             values.get(CHILD_MAIN[table]))
    touch_a3(a3_id, user)
    db.commit()


def delete_child(table, a3_id, row_id, user):
    db = get_db()
    old = get_child(table, row_id)
    if old is None or old["a3_id"] != a3_id:
        return
    db.execute(f"DELETE FROM {table} WHERE id = ? AND a3_id = ?", (row_id, a3_id))
    _log(db, a3_id, user, _child_step(table, old), table, row_id, "(deleted)", old[CHILD_MAIN[table]], None)
    touch_a3(a3_id, user)
    db.commit()


def load_bundle(a3_id):
    """A3 row plus all child rows, as plain dicts."""
    a3 = get_a3(a3_id)
    if a3 is None:
        return None
    bundle = {"a3": dict(a3)}
    for table in CHILD_TABLES:
        bundle[table] = [dict(r) for r in list_children(table, a3_id)]
    return bundle


# ---------- portfolio ----------

def all_open_actions():
    return get_db().execute(
        "SELECT action.*, a3.title AS a3_title, a3.department AS department FROM action "
        "JOIN a3 ON a3.id = action.a3_id "
        "WHERE action.status IN ('Open', 'In progress') AND a3.status NOT IN ('Closed', 'Cancelled') "
        "AND a3.is_template = 0 "
        "ORDER BY CASE WHEN action.due_date = '' THEN 1 ELSE 0 END, action.due_date"
    ).fetchall()


def all_lessons():
    return get_db().execute(
        "SELECT lesson.*, a3.title AS a3_title FROM lesson JOIN a3 ON a3.id = lesson.a3_id "
        "WHERE a3.is_template = 0 ORDER BY lesson.id DESC"
    ).fetchall()


def all_read_across():
    return get_db().execute(
        "SELECT read_across.*, a3.title AS a3_title FROM read_across JOIN a3 ON a3.id = read_across.a3_id "
        "WHERE a3.is_template = 0 ORDER BY read_across.status, read_across.due_date"
    ).fetchall()


# ---------- sign-off ----------

def add_signoff(a3_id, step, decision, comment, user):
    db = get_db()
    mark = db.execute("SELECT COALESCE(MAX(id), 0) FROM history WHERE a3_id = ?", (a3_id,)).fetchone()[0]
    db.execute("INSERT INTO signoff (a3_id, step, decision, comment, user, ts, hist_mark) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (a3_id, step, decision, comment, user, now(), mark))
    _log(db, a3_id, user, "", "signoff", None, f"sign-off {step.upper()}", None, f"{decision}: {comment}")
    db.commit()


def signoff_state(a3_id):
    """{step: {"row": latest sign-off, "stale": changed after sign-off, "approved": valid approval}}"""
    db = get_db()
    state = {}
    for step, _, _ in STEPS:
        row = db.execute("SELECT * FROM signoff WHERE a3_id = ? AND step = ? ORDER BY id DESC LIMIT 1",
                         (a3_id, step)).fetchone()
        stale = False
        if row:
            stale = db.execute("SELECT 1 FROM history WHERE a3_id = ? AND step = ? AND id > ? LIMIT 1",
                               (a3_id, step, row["hist_mark"])).fetchone() is not None
        state[step] = {"row": row, "stale": stale,
                       "approved": bool(row) and row["decision"] == "Approved" and not stale}
    return state


def list_signoffs(a3_id):
    return get_db().execute("SELECT * FROM signoff WHERE a3_id = ? ORDER BY id DESC", (a3_id,)).fetchall()


# ---------- users ----------

def count_users():
    return get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_user(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username):
    return get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def list_users():
    return get_db().execute("SELECT * FROM users ORDER BY active DESC, display_name").fetchall()


def create_user(username, display_name, password_hash, role):
    db = get_db()
    db.execute("INSERT INTO users (username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
               (username, display_name, password_hash, role, now()))
    db.commit()


def update_user(user_id, **values):
    cols = [c for c in values if c in ("display_name", "password_hash", "role", "active")]
    if cols:
        db = get_db()
        db.execute(f"UPDATE users SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
                   [values[c] for c in cols] + [user_id])
        db.commit()


# ---------- search ----------

def _like(q):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def search(q, limit=300):
    db = get_db()
    pat, ql = _like(q), q.lower()
    hits = []
    a3_cols = ["title"] + sorted(EDITABLE_COLUMNS - {"title"})
    where = " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in a3_cols)
    for r in db.execute(f"SELECT * FROM a3 WHERE {where}", [pat] * len(a3_cols)):
        for c in a3_cols:
            if ql in str(r[c]).lower():
                hits.append({"a3_id": r["id"], "a3_title": r["title"], "status": r["status"],
                             "table": "a3", "field": c, "text": str(r[c]), "step": FIELD_STEP.get(c, "general")})
    for table, cols in CHILD_TABLES.items():
        tcols = [c for c in cols if c not in NON_TEXT]
        where = " OR ".join(f"t.{c} LIKE ? ESCAPE '\\'" for c in tcols)
        sql = (f"SELECT t.*, a3.title AS a3_title, a3.status AS a3_status FROM {table} t "
               f"JOIN a3 ON a3.id = t.a3_id WHERE {where}")
        for r in db.execute(sql, [pat] * len(tcols)):
            for c in tcols:
                if ql in str(r[c]).lower():
                    hits.append({"a3_id": r["a3_id"], "a3_title": r["a3_title"], "status": r["a3_status"],
                                 "table": table, "field": c, "text": str(r[c]),
                                 "step": _child_step(table, r) or "general"})
    return hits[:limit]
