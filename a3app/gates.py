"""Quality-gate checks for each A3 step.

Every check has a stable id (e.g. "a.problem_quantified") so its level can be set to
required / advice / off in a3config.toml. "required" checks block step completion;
"advice" checks flag likely weaknesses that need human judgement.
"""
import re
from dataclasses import dataclass
from datetime import date


@dataclass
class GateCheck:
    id: str
    label: str
    passed: bool
    level: str = "required"  # required | advice
    hint: str = ""


PLACEHOLDER = re.compile(r"\[\[|\[UNVERIFIED", re.I)


SOLUTION_WORDS = re.compile(
    r"\b(implement|introduce|install|replace|retrain|train|need(s|ed)? to|should|must|add a|create a)\b", re.I
)
CAUSE_WORDS = re.compile(r"\b(because|due to|caused by|lack of|missing|insufficient|root cause)\b", re.I)
VAGUE_TARGETS = re.compile(r"^\s*(zero defects?|improve( quality)?|solve( the)? (issue|problem)|reduce)\s*\.?\s*$", re.I)
WEAK_ACTIONS = re.compile(
    r"\b(retrain|re-train|train(ing)?|increase attention|be more careful|monitor more closely|"
    r"raise awareness|awareness|update (the )?documentation|remind)\b", re.I
)
HAS_NUMBER = re.compile(r"\d")
NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def _filled(v):
    """Template placeholders ([[...]]) and unverified imports do not count as content."""
    return bool(v and str(v).strip()) and not PLACEHOLDER.search(str(v))


def parse_number(text):
    m = NUMBER.search(text or "")
    return float(m.group().replace(",", ".")) if m else None


def _overdue(row):
    try:
        return row["status"] in ("Open", "In progress") and date.fromisoformat(row["due_date"]) < date.today()
    except (ValueError, TypeError):
        return False


def gate_general(b, high):
    a3 = b["a3"]
    checks = [
        GateCheck("g.title", "Title filled", _filled(a3["title"])),
        GateCheck("g.title_neutral", "Title free of cause/solution wording",
                  not (SOLUTION_WORDS.search(a3["title"]) or CAUSE_WORDS.search(a3["title"])), "advice",
                  "The title should describe the gap, not an assumed cause or preferred solution."),
        GateCheck("g.champion", "Champion named", _filled(a3["champion"])),
        GateCheck("g.team_leader", "Team Leader named", _filled(a3["team_leader"])),
        GateCheck("g.team_members", "Team members listed", _filled(a3["team_members"]), "advice"),
        GateCheck("g.trigger", "Trigger recorded", _filled(a3["trigger"])),
        GateCheck("g.severity", "Severity recorded (from applicable criteria)", a3["severity"] != "Not assessed",
                  hint="The tool never assigns severity. Record the value from the SPS Trigger Matrix / rule."),
        GateCheck("g.scope", "Scope (in / out) defined", _filled(a3["scope_in"]) and _filled(a3["scope_out"])),
    ]
    if a3["trigger"] == "Customer request or complaint":
        checks.append(GateCheck(
            "g.customer_format", "Customer-specific format checked (A3 vs 8D / CQTS)",
            a3["customer_format_required"] != "Not checked",
            hint="Do not assume the internal A3 overrides a mandatory customer format."))
    if a3["a3_type"] == "Basic" and a3["severity"] in high:
        checks.append(GateCheck("g.basic_high_severity", "Basic A3 used for a high-severity case", False, "advice",
                                "Check the applicable trigger rules: high-severity cases usually need Standard/Extended."))
    return checks


def gate_a(b, high):
    a3 = b["a3"]
    ps = a3["problem_statement"]
    containment = [r for r in b["action"] if r["action_type"] == "Containment" and r["status"] != "Cancelled"]
    is_high = a3["severity"] in high
    checks = [
        GateCheck("a.background", "Background documented", _filled(a3["background"])),
        GateCheck("a.symptom", "Symptom described", _filled(a3["symptom"])),
        GateCheck("a.problem", "Problem statement filled", _filled(ps)),
        GateCheck("a.problem_quantified", "Problem statement is quantified", bool(HAS_NUMBER.search(ps or "")),
                  "advice", "Add frequency, magnitude, affected population or time range."),
        GateCheck("a.problem_no_solution", "Problem statement free of solution wording",
                  not SOLUTION_WORDS.search(ps or ""), "advice", "Do not let a solution define the problem."),
        GateCheck("a.problem_no_cause", "Problem statement free of assumed cause", not CAUSE_WORDS.search(ps or ""),
                  "advice", "Causes belong in Step B once verified."),
        GateCheck("a.expected", "Expected condition / standard stated", _filled(a3["expected_condition"])),
        GateCheck("a.data_sources", "Data sources named", _filled(a3["data_sources"])),
        GateCheck("a.is_is_not", "Is / Is Not captured", len(b["is_is_not"]) > 0, "advice",
                  "Recommended where the pattern helps narrow the cause."),
        GateCheck("a.containment", "Containment action defined (or documented as not needed)",
                  bool(containment) or _filled(a3["containment_exit_criteria"])),
        GateCheck("a.containment_owner", "Containment actions have owner and due date",
                  all(_filled(r["owner"]) and _filled(r["due_date"]) for r in containment)),
        GateCheck("a.containment_exit", "Containment exit criteria defined",
                  _filled(a3["containment_exit_criteria"]) or not containment),
        GateCheck("a.containment_effective", "Evidence that containment is working",
                  _filled(a3["containment_evidence"]) or not containment,
                  hint="E.g. sorting results, no further escapes since date X."),
        GateCheck("a.early_warning", "Early Warning assessed", a3["early_warning_assessed"] in ("Yes", "No"),
                  hint="Mandatory for high-severity cases." if is_high else ""),
        GateCheck("a.target_metric", "Target metric defined", _filled(a3["target_metric"])),
        GateCheck("a.target_baseline", "Baseline value defined", _filled(a3["target_baseline"])),
        GateCheck("a.target_value", "Target value defined", _filled(a3["target_value"])
                  and not VAGUE_TARGETS.match(a3["target_value"] or ""),
                  hint="'Zero defects' / 'improve' need an operational definition and measurement approach."),
        GateCheck("a.target_date", "Target date defined", _filled(a3["target_date"])),
    ]
    if is_high:
        checks.append(GateCheck("a.early_warning_notes", "High severity: Early Warning notes recorded",
                                _filled(a3["early_warning_notes"]),
                                hint="Record recipients / cross-organizational notification decision."))
    return checks


def _verified(b, category):
    return [h for h in b["hypothesis"] if h["category"] == category and h["status"] == "Verified"]


def gate_b(b, high):
    a3 = b["a3"]
    hyps = b["hypothesis"]
    tested = [h for h in hyps if h["status"] in ("Verified", "Excluded", "Inconclusive")]
    verified_without_evidence = [h for h in hyps if h["status"] == "Verified" and not _filled(h["evidence"])]
    verified_ids = {h["id"] for h in hyps if h["status"] == "Verified"}
    whys = b["why_step"]
    chains = {w["cause_id"] for w in whys}
    unsupported = [w for w in whys if w["status"] != "Supported"]
    return [
        GateCheck("b.hypotheses", "Hypotheses recorded", len(hyps) > 0),
        GateCheck("b.multiple_hypotheses", "More than one hypothesis considered", len(hyps) > 1, "advice",
                  "Alternative plausible causes should be considered."),
        GateCheck("b.tested", "Key hypotheses tested", len(tested) > 0),
        GateCheck("b.verified_evidence", "Every verified cause has evidence", not verified_without_evidence,
                  hint=", ".join(f"#{h['id']}" for h in verified_without_evidence)),
        GateCheck("b.occurrence", "Technical occurrence cause verified", bool(_verified(b, "Occurrence"))),
        GateCheck("b.detection", "Detection / escape cause verified or justified N/A",
                  bool(_verified(b, "Detection / escape")) or _filled(a3["detection_na_justification"])),
        GateCheck("b.systemic", "Systemic cause verified or absence justified",
                  bool(_verified(b, "Systemic")) or _filled(a3["systemic_na_justification"])),
        GateCheck("b.methods", "Methods documented", _filled(a3["methods_used"]), "advice"),
        GateCheck("b.none_pending", "No hypotheses left 'Prioritized for verification'",
                  not any(h["status"] == "Prioritized for verification" for h in hyps), "advice"),
        GateCheck("b.why_chain", "Why-Why chain starts from a verified cause", bool(chains & verified_ids), "advice",
                  "Start each chain from a cause with status Verified."),
        GateCheck("b.why_supported", "Every Why-Why step is supported by evidence", not unsupported, "advice",
                  "Unsupported/unverified steps: " + ", ".join(f"#{w['id']}" for w in unsupported) if unsupported else ""),
        GateCheck("b.why_root", "Why-Why chain reaches a technical or systemic root cause",
                  not whys or any(w["is_root"] != "No" for w in whys), "advice"),
    ]


def gate_c(b, high):
    a3 = b["a3"]
    verified_ids = {h["id"] for h in b["hypothesis"] if h["status"] == "Verified"}
    corrective = [r for r in b["action"] if r["action_type"] in ("Correction", "Technical corrective",
                                                                  "Systemic / preventive")
                  and r["status"] != "Cancelled"]
    unlinked = [r for r in corrective if r["cause_id"] not in verified_ids]
    uncovered = [i for i in verified_ids if not any(r["cause_id"] == i for r in corrective)]
    weak = [r for r in corrective if WEAK_ACTIONS.search(r["description"]) and not _filled(r["expected_result"])]
    return [
        GateCheck("c.actions", "Corrective actions defined", bool(corrective)),
        GateCheck("c.linked", "Every action linked to a verified cause", not unlinked,
                  hint="Unlinked: " + ", ".join(f"#{r['id']}" for r in unlinked) if unlinked else ""),
        GateCheck("c.covered", "Every verified cause has an action", not uncovered,
                  hint="Uncovered causes: " + ", ".join(f"#{i}" for i in uncovered) if uncovered else ""),
        GateCheck("c.owners", "Owners and due dates defined",
                  all(_filled(r["owner"]) and _filled(r["due_date"]) for r in corrective)),
        GateCheck("c.verification_plan", "Expected result / verification plan defined",
                  all(_filled(r["expected_result"]) for r in corrective)),
        GateCheck("c.weak_actions", "No weak awareness/retraining-only actions without effectiveness criteria",
                  not weak, "advice",
                  "Retrain / monitor / update documentation is only acceptable if it addresses the verified cause."),
        GateCheck("c.alternatives", "Alternatives and decision rationale recorded",
                  _filled(a3["solution_alternatives"]) and _filled(a3["decision_rationale"]), "advice"),
        GateCheck("c.risks", "Risks / side effects considered", _filled(a3["risks_side_effects"])),
    ]


def kpi_status(b):
    """(latest value, target, meets_target or None if not determinable)"""
    a3 = b["a3"]
    values = [m for m in b["measurement"] if m["value"] is not None]
    target = parse_number(a3["target_value"])
    if not values or target is None:
        return (values[-1]["value"] if values else None), target, None
    latest = values[-1]["value"]
    lower = a3.get("target_direction", "Lower is better") == "Lower is better"
    return latest, target, (latest <= target if lower else latest >= target)


def gate_d(b, high):
    a3 = b["a3"]
    active = [r for r in b["action"] if r["status"] != "Cancelled"]
    corrective = [r for r in active if r["action_type"] in ("Correction", "Technical corrective",
                                                             "Systemic / preventive")]
    containment = [r for r in active if r["action_type"] == "Containment"]
    target_ok = a3["target_achieved"] == "Yes" or (a3["target_achieved"] == "No" and _filled(a3["deviation_acceptance"]))
    ll_ok = (a3["lessons_learned_required"] == "Yes" and bool(b["lesson"])) or (
        a3["lessons_learned_required"] == "No" and _filled(a3["lessons_learned_no_reason"]))
    _, _, meets = kpi_status(b)
    return [
        GateCheck("d.actions_done", "All actions completed", all(r["status"] == "Done" for r in active)),
        GateCheck("d.effective", "Corrective actions validated as effective",
                  bool(corrective) and all(r["effectiveness"] == "Effective" for r in corrective),
                  hint="Implementation date is not proof of effectiveness."),
        GateCheck("d.observed", "Observed result and observation window recorded",
                  _filled(a3["observed_result"]) and _filled(a3["observation_window"])),
        GateCheck("d.evidence", "Evidence of effectiveness referenced", _filled(a3["effect_evidence"])),
        GateCheck("d.kpi_recorded", "KPI measurements recorded against the Step A target",
                  len(b["measurement"]) > 0, "advice"),
        GateCheck("d.kpi_meets_target", "Latest KPI measurement meets the target", meets is not False, "advice",
                  "Check target value / direction and the latest measurement."),
        GateCheck("d.target", "Step A target achieved or deviation accepted", target_ok),
        GateCheck("d.recurrence", "Non-recurrence checked", _filled(a3["recurrence_check"])),
        GateCheck("d.containment_removed", "Containment removed after validation",
                  not containment or a3["containment_removed"] == "Yes"),
        GateCheck("d.standardization", "Standardization / systemic prevention addressed",
                  _filled(a3["standardization"])),
        GateCheck("d.read_across", "Read Across assessed", a3["read_across_assessed"] == "Yes"),
        GateCheck("d.read_across_closed", "Read Across items closed",
                  all(r["status"] in ("Done", "Not applicable") for r in b["read_across"])),
        GateCheck("d.lessons", "Lessons Learned addressed (item or documented reason)", ll_ok),
        GateCheck("d.champion_feedback", "Champion feedback recorded", _filled(a3["champion_feedback"]), "advice"),
    ]


GATES = {"general": gate_general, "a": gate_a, "b": gate_b, "c": gate_c, "d": gate_d}


def evaluate(bundle, cfg=None):
    """Return {step: {"checks": [...], "ready": bool}} with config levels applied."""
    cfg = cfg or {}
    high = cfg.get("severity", {}).get("high", ["1", "2"])
    levels = dict(cfg.get("checks", {}))
    levels.update(cfg.get("a3_types", {}).get(bundle["a3"]["a3_type"], {}).get("checks", {}))
    result = {}
    for step, fn in GATES.items():
        checks = []
        for c in fn(bundle, high):
            c.level = levels.get(c.id, c.level)
            if c.level != "off":
                checks.append(c)
        result[step] = {"checks": checks, "ready": all(c.passed for c in checks if c.level == "required")}
    return result


def readiness(evaluation):
    ready = sum(1 for v in evaluation.values() if v["ready"])
    if ready == len(evaluation):
        return "Ready"
    return "Not ready" if ready <= 1 else "Partially ready"


def overdue_actions(bundle):
    return [r for r in bundle["action"] if _overdue(r)]


def alerts(bundle, cfg=None):
    """Process alerts that are not step gates (severity escalation etc.)."""
    a3 = bundle["a3"]
    high = (cfg or {}).get("severity", {}).get("high", ["1", "2"])
    msgs = []
    if a3["severity"] in high:
        msgs.append(f"Severity {a3['severity']} recorded (high): Early Warning assessment is mandatory, check "
                    "cross-organizational notification, document in myA3Creator, and check Fast Track Learning / "
                    "Read Across escalation.")
    if a3["customer_format_required"] in ("8D required (CQTS)", "Other customer format required"):
        msgs.append("A customer-specific format is required. This A3 does not replace the mandatory customer "
                    "documentation (e.g. 8D in CQTS).")
    n = len(overdue_actions(bundle))
    if n:
        msgs.append(f"{n} action(s) overdue.")
    if any(PLACEHOLDER.search(str(v)) for v in a3.values() if isinstance(v, str)):
        msgs.append("This A3 contains template placeholders [[...]] or [UNVERIFIED IMPORT] text. "
                    "Those fields count as empty until reviewed and edited.")
    return msgs
