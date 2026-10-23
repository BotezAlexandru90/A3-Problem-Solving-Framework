from datetime import date

from flask import (Blueprint, Response, abort, current_app, flash, redirect, render_template, request, send_file,
                   url_for)

from . import db, gates, importer, stats
from .auth import can_signoff, has_role, require, user_name
from .charts import kpi_chart
from .export import to_markdown, to_xlsx
from .model import CHILD_FIELDS, CHILD_LABELS, CHILD_MAIN, STATUSES, STEPS

bp = Blueprint("a3", __name__)

STEP_KEYS = [s[0] for s in STEPS]
STEP_LABEL = {s[0]: s[1] for s in STEPS}
STEP_STATUS = {"a": "Step A", "b": "Step B", "c": "Step C", "d": "Step D"}
STEP_CHILDREN = {
    "general": [],
    "a": [("is_is_not", None), ("action", ["Containment"])],
    "b": [("hypothesis", None), ("why_step", None)],
    "c": [("action", ["Correction", "Technical corrective", "Systemic / preventive"])],
    "d": [("measurement", None), ("action", ["Validation", "Standardization"]), ("read_across", None),
          ("lesson", None)],
}
ORDER = ["Step A", "Step B", "Step C", "Step D", "Closed"]


def _cfg():
    return current_app.config["A3"]


def _opts():
    return current_app.config["A3_OPTIONS"]


def _type_cfg(a3):
    return _cfg()["a3_types"].get(a3["a3_type"], {"hidden_fields": [], "hidden_sections": []})


def _evaluate(bundle):
    return gates.evaluate(bundle, _cfg())


def _bundle_or_404(a3_id):
    bundle = db.load_bundle(a3_id)
    if bundle is None:
        abort(404)
    return bundle


def _version():
    try:
        return int(request.form.get("version", 0))
    except ValueError:
        abort(400)


def _clean(fields, form, a3_id=None):
    """Validate the submitted subset of fields; returns (values, errors)."""
    values, errors = {}, []
    opts = _opts()
    for name, label, widget in fields:
        if name not in form:
            continue
        raw = form.get(name, "").strip()
        if widget.startswith("select:"):
            if raw not in opts[widget.split(":", 1)[1]]:
                errors.append(f"Invalid value for '{label}'.")
                continue
        elif widget == "date" and raw:
            try:
                date.fromisoformat(raw)
            except ValueError:
                errors.append(f"'{label}' must be a date (YYYY-MM-DD).")
                continue
        elif widget == "int":
            try:
                values[name] = int(raw or 1)
            except ValueError:
                errors.append(f"'{label}' must be a whole number.")
            continue
        elif widget == "number":
            try:
                values[name] = float(raw.replace(",", "."))
            except ValueError:
                errors.append(f"'{label}' must be a number.")
            continue
        elif widget == "cause":
            if not raw:
                values[name] = None
                continue
            row = db.get_child("hypothesis", int(raw)) if raw.isdigit() else None
            if row is None or row["a3_id"] != a3_id:
                errors.append("Linked cause does not belong to this A3.")
                continue
            values[name] = row["id"]
            continue
        values[name] = raw[:20000]
    return values, errors


def _flash_errors(errors):
    for e in errors:
        flash(e, "error")


@bp.get("/")
def dashboard():
    status_filter = request.args.get("status", "open")
    rows = []
    all_a3s = db.list_a3s()
    for a3 in all_a3s:
        if status_filter == "open" and a3["status"] in ("Closed", "Cancelled"):
            continue
        if status_filter not in ("open", "all") and a3["status"] != status_filter:
            continue
        bundle = db.load_bundle(a3["id"])
        ev = _evaluate(bundle)
        rows.append({
            "a3": a3,
            "gates": {k: v["ready"] for k, v in ev.items()},
            "open_actions": sum(1 for r in bundle["action"] if r["status"] in ("Open", "In progress")),
            "overdue": len(gates.overdue_actions(bundle)),
            "readiness": gates.readiness(ev),
        })
    counts = {}
    for a3 in all_a3s:
        counts[a3["status"]] = counts.get(a3["status"], 0) + 1
    return render_template("dashboard.html", rows=rows, status_filter=status_filter, statuses=STATUSES,
                           counts=counts, steps=STEPS, templates=db.list_a3s(templates=True))


@bp.post("/a3/new")
@require("member")
def new_a3():
    title = request.form.get("title", "").strip()
    if not title:
        flash("A title describing the problem / gap is required.", "error")
        return redirect(url_for("a3.dashboard"))
    copy_from = None
    template_id = request.form.get("template_id", "")
    if template_id.isdigit():
        tpl = db.get_a3(int(template_id))
        if tpl is None or not tpl["is_template"]:
            abort(400)
        copy_from = dict(tpl)
    a3_id = db.create_a3(title[:300], user_name(), copy_from)
    return redirect(url_for("a3.view", a3_id=a3_id, tab="general"))


def _fishbone(bundle):
    cats = _cfg()["picklists"]["fishbone_categories"]
    groups = {c: [] for c in cats}
    unassigned = []
    for h in bundle["hypothesis"]:
        (groups[h["fishbone"]] if h["fishbone"] in groups else unassigned).append(h)
    return {"groups": groups, "unassigned": unassigned}


def _why_chains(bundle):
    chains = {}
    for w in bundle["why_step"]:
        chains.setdefault(w["cause_id"], []).append(w)
    return chains


@bp.get("/a3/<int:a3_id>")
def view(a3_id):
    tab = request.args.get("tab", "general")
    if tab not in STEP_KEYS:
        abort(404)
    bundle = _bundle_or_404(a3_id)
    a3 = bundle["a3"]
    tcfg = _type_cfg(a3)
    ev = _evaluate(bundle)
    step = next(s for s in STEPS if s[0] == tab)
    fields = [f for f in step[2] if f[0] not in tcfg["hidden_fields"]]
    children = []
    for table, types in STEP_CHILDREN[tab]:
        if table in tcfg["hidden_sections"]:
            continue
        rows = bundle[table]
        if types:
            rows = [r for r in rows if r["action_type"] in types]
        children.append({"table": table, "label": CHILD_LABELS[table], "rows": rows, "types": types,
                         "fields": CHILD_FIELDS[table]})
    extra = {}
    if tab == "b":
        if "fishbone" not in tcfg["hidden_sections"]:
            extra["fishbone"] = _fishbone(bundle)
        extra["why_chains"] = _why_chains(bundle)
    if tab == "d":
        latest, target, meets = gates.kpi_status(bundle)
        extra["chart"] = kpi_chart(bundle["measurement"], gates.parse_number(a3["target_baseline"]), target)
        extra["kpi"] = {"latest": latest, "target": target, "meets": meets}
    return render_template("a3.html", b=bundle, a3=a3, tab=tab, step=step, fields=fields, steps=STEPS, ev=ev,
                           options=_opts(), children=children, hyp_index={h["id"]: h for h in bundle["hypothesis"]},
                           alerts=gates.alerts(bundle, _cfg()), readiness=gates.readiness(ev), statuses=STATUSES,
                           today=date.today().isoformat(), signoffs=db.signoff_state(a3_id),
                           signoff_steps=_cfg()["workflow"]["signoff_steps"], can_edit=has_role("member"),
                           **extra)


@bp.post("/a3/<int:a3_id>/save")
@require("member")
def save(a3_id):
    tab = request.form.get("tab", "general")
    if tab not in STEP_KEYS:
        abort(400)
    _bundle_or_404(a3_id)
    fields = next(s[2] for s in STEPS if s[0] == tab)
    values, errors = _clean(fields, request.form, a3_id)
    if tab == "general" and not values.get("title"):
        errors.append("Title is required.")
    if errors:
        _flash_errors(errors)
        return redirect(url_for("a3.view", a3_id=a3_id, tab=tab))
    try:
        db.update_a3(a3_id, _version(), values, user_name())
        flash("Saved.", "ok")
    except db.ConflictError:
        flash("This A3 was changed by someone else since you opened it. Your changes were NOT saved. "
              "Reload and re-apply them.", "error")
    return redirect(url_for("a3.view", a3_id=a3_id, tab=tab))


@bp.post("/a3/<int:a3_id>/status")
@require("team_leader")
def set_status(a3_id):
    bundle = _bundle_or_404(a3_id)
    a3 = bundle["a3"]
    target = request.form.get("status", "")
    if target not in STATUSES:
        abort(400)
    back_tab = request.form.get("tab", "general")
    if a3["is_template"]:
        flash("Templates have no workflow status.", "error")
        return redirect(url_for("a3.view", a3_id=a3_id, tab=back_tab))
    forward = a3["status"] not in ORDER or (target in ORDER and ORDER.index(target) > ORDER.index(a3["status"]))
    if target in ORDER and forward:
        # Steps must be completed in sequence: every gate (and sign-off) up to the target must pass.
        done_steps = STEP_KEYS[1:ORDER.index(target) + 1]
        ev = _evaluate(bundle)
        problems = [f"quality gate open for {STEP_LABEL[k]}" for k in ["general"] + done_steps if not ev[k]["ready"]]
        wf = _cfg()["workflow"]
        if wf["require_signoff_to_advance"]:
            state = db.signoff_state(a3_id)
            problems += [f"no valid Champion sign-off for {STEP_LABEL[k]}" for k in done_steps
                         if k in wf["signoff_steps"] and not state[k]["approved"]]
        if problems:
            flash(f"Cannot move to '{target}': " + "; ".join(problems) + ".", "error")
            return redirect(url_for("a3.view", a3_id=a3_id, tab=back_tab))
    values = {"status": target, "closed_date": date.today().isoformat() if target == "Closed" else ""}
    try:
        db.update_a3(a3_id, _version(), values, user_name())
        flash(f"Status set to {target}.", "ok")
    except db.ConflictError:
        flash("This A3 was changed by someone else. Reload and try again.", "error")
    tab = {v: k for k, v in STEP_STATUS.items()}.get(target, "d")
    return redirect(url_for("a3.view", a3_id=a3_id, tab=tab))


@bp.post("/a3/<int:a3_id>/signoff")
def signoff(a3_id):
    if not can_signoff():
        abort(403)
    bundle = _bundle_or_404(a3_id)
    step = request.form.get("step", "")
    decision = request.form.get("decision", "")
    comment = request.form.get("comment", "").strip()[:4000]
    if step not in _cfg()["workflow"]["signoff_steps"] or decision not in _opts()["SIGNOFF_DECISIONS"]:
        abort(400)
    if decision == "Approved" and not _evaluate(bundle)[step]["ready"]:
        flash("Cannot approve: required quality-gate checks of this step are still open.", "error")
    elif decision != "Approved" and not comment:
        flash("Please state what needs rework.", "error")
    else:
        db.add_signoff(a3_id, step, decision, comment, user_name())
        flash(f"Sign-off recorded: {decision}.", "ok")
    return redirect(url_for("a3.view", a3_id=a3_id, tab=step))


@bp.get("/a3/<int:a3_id>/history")
def history(a3_id):
    bundle = _bundle_or_404(a3_id)
    return render_template("history.html", a3=bundle["a3"], rows=db.list_history(a3_id),
                           signoffs=db.list_signoffs(a3_id), step_label=STEP_LABEL)


@bp.post("/a3/<int:a3_id>/duplicate")
@require("member")
def duplicate(a3_id):
    src = _bundle_or_404(a3_id)["a3"]
    title = request.form.get("title", "").strip()[:300]
    steps = [s for s in request.form.getlist("steps") if s in STEP_KEYS]
    if not title:
        flash("A title is required for the copy.", "error")
        return redirect(url_for("a3.view", a3_id=a3_id, tab="general"))
    copy = {f[0]: src[f[0]] for s in STEPS if s[0] in steps for f in s[2]}
    new_id = db.create_a3(title, user_name(), copy)
    flash(f"Copied from A3 #{a3_id}. Review every copied field: facts of the original may not apply.", "ok")
    return redirect(url_for("a3.view", a3_id=new_id, tab="general"))


@bp.post("/a3/<int:a3_id>/template")
@require("team_leader")
def toggle_template(a3_id):
    a3 = _bundle_or_404(a3_id)["a3"]
    try:
        db.update_a3(a3_id, _version(), {"is_template": 0 if a3["is_template"] else 1}, user_name())
        flash("Template flag changed.", "ok")
    except db.ConflictError:
        flash("This A3 was changed by someone else. Reload and try again.", "error")
    return redirect(url_for("a3.view", a3_id=a3_id, tab="general"))


@bp.post("/a3/<int:a3_id>/delete")
@require("admin")
def delete(a3_id):
    _bundle_or_404(a3_id)
    if request.form.get("confirm_title", "").strip() != db.get_a3(a3_id)["title"]:
        flash("Type the exact A3 title to confirm deletion.", "error")
        return redirect(url_for("a3.view", a3_id=a3_id, tab="general"))
    db.delete_a3(a3_id, user_name())
    flash("A3 deleted.", "ok")
    return redirect(url_for("a3.dashboard"))


# ---------- draft from notes ----------

@bp.route("/a3/<int:a3_id>/import", methods=["GET", "POST"])
@require("member")
def import_notes(a3_id):
    bundle = _bundle_or_404(a3_id)
    a3 = bundle["a3"]
    if request.method == "GET":
        return render_template("import.html", a3=a3, sentences=None)
    if request.form.get("stage") == "apply":
        return _apply_import(a3)
    text = request.form.get("text", "")
    upload = request.files.get("file")
    if upload and upload.filename:
        try:
            text += "\n" + importer.extract_text(upload.filename, upload.read())
        except Exception as exc:  # noqa: BLE001 - any parser failure is reported to the user
            flash(f"Could not read the file: {exc}", "error")
            return render_template("import.html", a3=a3, sentences=None)
    sentences = [(s, importer.classify(s)) for s in importer.split_sentences(text)]
    if not sentences:
        flash("No usable text found.", "error")
    return render_template("import.html", a3=a3, sentences=sentences, targets=importer.TARGETS)


def _apply_import(a3):
    a3_id = a3["id"]
    appended, children = {}, []
    for i in range(importer.MAX_SENTENCES):
        s = request.form.get(f"s{i}")
        if s is None:
            break
        target = request.form.get(f"t{i}", "skip")
        if target not in importer.TARGET_KEYS or target == "skip":
            continue
        line = f"{importer.MARK} {s.strip()[:1000]}"
        if target == "containment":
            children.append(("action", {"action_type": "Containment", "description": line, "status": "Open",
                                        "effectiveness": "Not assessed"}))
        elif target == "hypothesis":
            children.append(("hypothesis", {"category": "Occurrence", "hypothesis": line, "status": "Untested"}))
        else:
            appended.setdefault(target, []).append(line)
    if appended:
        values = {f: "\n".join(([a3[f]] if a3[f] else []) + lines) for f, lines in appended.items()}
        try:
            db.update_a3(a3_id, _version(), values, user_name())
        except db.ConflictError:
            flash("This A3 was changed by someone else meanwhile. Nothing was imported; please retry.", "error")
            return redirect(url_for("a3.view", a3_id=a3_id, tab="a"))
    for table, values in children:
        db.save_child(table, a3_id, None, values, user_name())
    flash(f"Imported {sum(len(v) for v in appended.values()) + len(children)} item(s), all marked "
          f"{importer.MARK}. Verify and edit each one; marked fields count as empty for the quality gates.", "ok")
    return redirect(url_for("a3.view", a3_id=a3_id, tab="a"))


# ---------- child rows ----------

def _check_table(table):
    if table not in CHILD_FIELDS:
        abort(404)


@bp.route("/a3/<int:a3_id>/<table>/edit", methods=["GET", "POST"])
@bp.route("/a3/<int:a3_id>/<table>/<int:row_id>/edit", methods=["GET", "POST"])
@require("member")
def edit_child(a3_id, table, row_id=None):
    _check_table(table)
    bundle = _bundle_or_404(a3_id)
    tab = request.values.get("tab", "general")
    if tab not in STEP_KEYS:
        tab = "general"
    row = None
    if row_id:
        row = db.get_child(table, row_id)
        if row is None or row["a3_id"] != a3_id:
            abort(404)
    fields = CHILD_FIELDS[table]
    if request.method == "POST":
        values, errors = _clean(fields, request.form, a3_id)
        if values.get(CHILD_MAIN[table]) in (None, ""):
            errors.append("The main field is required.")
        if not errors:
            db.save_child(table, a3_id, row_id, values, user_name())
            flash(f"{CHILD_LABELS[table]} saved.", "ok")
            return redirect(url_for("a3.view", a3_id=a3_id, tab=tab))
        _flash_errors(errors)
        row = dict(request.form)
    types = request.args.getlist("type")
    hyps = bundle["hypothesis"]
    if table == "why_step":
        hyps = [h for h in hyps if h["status"] == "Verified"] or hyps
    return render_template("child_form.html", a3=bundle["a3"], table=table, label=CHILD_LABELS[table],
                           fields=fields, row=row, row_id=row_id, tab=tab, options=_opts(),
                           hypotheses=hyps, types=types)


@bp.post("/a3/<int:a3_id>/<table>/<int:row_id>/delete")
@require("member")
def delete_child(a3_id, table, row_id):
    _check_table(table)
    _bundle_or_404(a3_id)
    db.delete_child(table, a3_id, row_id, user_name())
    flash(f"{CHILD_LABELS[table]} deleted.", "ok")
    return redirect(url_for("a3.view", a3_id=a3_id, tab=request.form.get("tab", "general")))


# ---------- registers, search, statistics ----------

@bp.get("/actions")
def actions():
    rows = db.all_open_actions()
    return render_template("actions.html", rows=rows, today=date.today().isoformat())


@bp.get("/lessons")
def lessons():
    return render_template("lessons.html", rows=db.all_lessons())


@bp.get("/read-across")
def read_across():
    return render_template("read_across.html", rows=db.all_read_across(), today=date.today().isoformat())


@bp.get("/search")
def search():
    q = request.args.get("q", "").strip()[:200]
    hits = db.search(q) if len(q) >= 2 else []
    labels = {f[0]: f[1] for s in STEPS for f in s[2]}
    for table, flist in CHILD_FIELDS.items():
        for name, label, _ in flist:
            labels[f"{table}.{name}"] = f"{CHILD_LABELS[table]}: {label}"
    for h in hits:
        key = h["field"] if h["table"] == "a3" else f"{h['table']}.{h['field']}"
        h["label"] = labels.get(key, key)
        i = h["text"].lower().find(q.lower())
        start = max(0, i - 80)
        h["before"], h["match"], h["after"] = (h["text"][start:i], h["text"][i:i + len(q)],
                                                h["text"][i + len(q):i + len(q) + 120])
    return render_template("search.html", q=q, hits=hits)


@bp.get("/stats")
def statistics():
    return render_template("stats.html", s=stats.compute(_cfg()))


# ---------- export ----------

@bp.get("/a3/<int:a3_id>/export.md")
def export_md(a3_id):
    bundle = _bundle_or_404(a3_id)
    md = to_markdown(bundle, _evaluate(bundle))
    return Response(md, mimetype="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=A3_{a3_id}.md"})


@bp.get("/a3/<int:a3_id>/export.xlsx")
def export_xlsx(a3_id):
    bundle = _bundle_or_404(a3_id)
    return send_file(to_xlsx(bundle, _evaluate(bundle)), as_attachment=True,
                     download_name=f"A3_{a3_id}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.get("/a3/<int:a3_id>/print")
def print_view(a3_id):
    bundle = _bundle_or_404(a3_id)
    ev = _evaluate(bundle)
    a3 = bundle["a3"]
    chart = kpi_chart(bundle["measurement"], gates.parse_number(a3["target_baseline"]),
                      gates.parse_number(a3["target_value"]))
    return render_template("print.html", b=bundle, a3=a3, steps=STEPS, ev=ev,
                           child_fields=CHILD_FIELDS, child_labels=CHILD_LABELS,
                           readiness=gates.readiness(ev), alerts=gates.alerts(bundle, _cfg()),
                           signoffs=db.signoff_state(a3_id), chart=chart)
