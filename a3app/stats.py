"""Portfolio statistics (templates excluded)."""
from collections import Counter, defaultdict
from datetime import date, datetime

from . import db, gates

STEP_STATES = ["Step A", "Step B", "Step C", "Step D"]


def _d(text):
    try:
        return datetime.fromisoformat(text).date() if "T" in text else date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def compute(cfg):
    today = date.today()
    a3s = db.list_a3s()
    by = {k: Counter() for k in ("status", "severity", "trigger", "department", "a3_type")}
    for a in a3s:
        for k in by:
            by[k][a[k] or "(blank)"] += 1

    open_a3s = [a for a in a3s if a["status"] not in ("Closed", "Cancelled")]
    ages = sorted((((today - (_d(a["start_date"]) or _d(a["created_at"]))).days, a) for a in open_a3s),
                  key=lambda t: t[0])
    closed = [a for a in a3s if a["status"] == "Closed"]
    lead_times = [(_d(a["closed_date"]) - (_d(a["start_date"]) or _d(a["created_at"]))).days
                  for a in closed if _d(a["closed_date"])]
    closed_90 = [a for a in closed if _d(a["closed_date"]) and (today - _d(a["closed_date"])).days <= 90]

    # Days spent per step, from status changes in the change history.
    events = defaultdict(list)
    for h in db.status_history():
        events[h["a3_id"]].append((h["ts"], h["new_value"]))
    durations = defaultdict(list)
    for a in a3s:
        timeline = [(a["created_at"], "Step A")] + events.get(a["id"], [])
        for i, (ts, state) in enumerate(timeline):
            end = timeline[i + 1][0] if i + 1 < len(timeline) else None
            if state not in STEP_STATES or (end is None and a["status"] in ("Closed", "Cancelled")):
                continue
            end_d = _d(end) if end else today
            durations[state].append((end_d - _d(ts)).days)
    step_days = {s: (round(sum(v) / len(v), 1) if v else None, len(v)) for s, v in
                 ((s, durations.get(s, [])) for s in STEP_STATES)}

    overdue_owner, overdue_dept = Counter(), Counter()
    for r in db.all_open_actions():
        if gates._overdue(r):
            overdue_owner[r["owner"] or "(no owner)"] += 1
            overdue_dept[r["department"] or "(blank)"] += 1

    readiness = Counter()
    for a in open_a3s:
        readiness[gates.readiness(gates.evaluate(db.load_bundle(a["id"]), cfg))] += 1

    total_decided = len(closed) + len(open_a3s)
    return {
        "total": len(a3s), "open": len(open_a3s), "closed": len(closed),
        "closure_rate": round(100 * len(closed) / total_decided) if total_decided else None,
        "closed_90": len(closed_90),
        "avg_lead": round(sum(lead_times) / len(lead_times)) if lead_times else None,
        "avg_age": round(sum(a for a, _ in ages) / len(ages)) if ages else None,
        "oldest": list(reversed(ages))[:10],
        "by": {k: v.most_common() for k, v in by.items()},
        "step_days": step_days,
        "overdue_owner": overdue_owner.most_common(), "overdue_dept": overdue_dept.most_common(),
        "readiness": readiness.most_common(),
    }
