from a3app.gates import evaluate


def _bundle(**a3):
    base = {k: "" for k in [
        "title", "champion", "team_leader", "team_members", "trigger", "scope_in", "scope_out",
        "background", "symptom", "problem_statement", "expected_condition", "data_sources",
        "containment_exit_criteria", "containment_evidence", "early_warning_notes", "target_metric",
        "target_baseline", "target_value",
        "target_date", "methods_used", "detection_na_justification", "systemic_na_justification",
        "solution_alternatives", "decision_rationale", "risks_side_effects", "observed_result",
        "observation_window", "effect_evidence", "deviation_acceptance", "recurrence_check", "standardization",
        "lessons_learned_no_reason", "champion_feedback"]}
    base.update(severity="Not assessed", a3_type="Standard", customer_format_required="Not checked",
                early_warning_assessed="Not assessed", target_achieved="Not assessed", containment_removed="No",
                read_across_assessed="No", lessons_learned_required="Not assessed",
                target_direction="Lower is better")
    base.update(a3)
    return {"a3": base, "is_is_not": [], "hypothesis": [], "action": [], "read_across": [], "lesson": [],
            "why_step": [], "measurement": []}


def test_empty_a3_fails_all_gates():
    ev = evaluate(_bundle(title="Gap"))
    assert not any(v["ready"] for v in ev.values())


def test_step_b_requires_verified_occurrence_and_justifications():
    b = _bundle()
    b["hypothesis"] = [{"id": 1, "category": "Occurrence", "status": "Verified", "evidence": "Test report 42"}]
    assert not evaluate(b)["b"]["ready"]
    b["a3"]["detection_na_justification"] = "No detection step exists by design; covered in systemic cause."
    b["a3"]["systemic_na_justification"] = "n/a justified"
    assert evaluate(b)["b"]["ready"]


def test_verified_without_evidence_fails():
    b = _bundle(detection_na_justification="x", systemic_na_justification="x")
    b["hypothesis"] = [{"id": 1, "category": "Occurrence", "status": "Verified", "evidence": ""}]
    assert not evaluate(b)["b"]["ready"]


def test_step_c_action_must_link_verified_cause():
    b = _bundle(risks_side_effects="none identified")
    b["hypothesis"] = [{"id": 1, "category": "Occurrence", "status": "Untested", "evidence": ""}]
    b["action"] = [{"id": 1, "action_type": "Technical corrective", "description": "Change torque", "cause_id": 1,
                    "owner": "A", "due_date": "2026-12-01", "status": "Open", "expected_result": "ppm<10",
                    "effectiveness": "Not assessed"}]
    assert not evaluate(b)["c"]["ready"]
    b["hypothesis"][0]["status"] = "Verified"
    assert evaluate(b)["c"]["ready"]


def test_step_d_done_is_not_effective():
    b = _bundle(observed_result="8 ppm", observation_window="3 months", effect_evidence="SPC chart",
                target_achieved="Yes", recurrence_check="none", standardization="CP rev C",
                read_across_assessed="Yes", lessons_learned_required="No", lessons_learned_no_reason="covered")
    b["action"] = [{"id": 1, "action_type": "Technical corrective", "description": "x", "cause_id": 1,
                    "owner": "A", "due_date": "2026-01-01", "status": "Done", "expected_result": "y",
                    "effectiveness": "Not assessed"}]
    assert not evaluate(b)["d"]["ready"]
    b["action"][0]["effectiveness"] = "Effective"
    assert evaluate(b)["d"]["ready"]


def test_placeholders_count_as_empty():
    b = _bundle(background="[[Describe what happened]]")
    assert not next(c for c in evaluate(b)["a"]["checks"] if c.id == "a.background").passed
    b["a3"]["background"] = "[UNVERIFIED IMPORT] Customer called"
    assert not next(c for c in evaluate(b)["a"]["checks"] if c.id == "a.background").passed


def test_config_levels_and_type_overrides():
    cfg = {"checks": {"a.problem_quantified": "required"},
           "a3_types": {"Basic": {"checks": {"a.is_is_not": "off"}}}, "severity": {"high": ["1"]}}
    b = _bundle(a3_type="Basic")
    checks = {c.id: c for c in evaluate(b, cfg)["a"]["checks"]}
    assert checks["a.problem_quantified"].level == "required"
    assert "a.is_is_not" not in checks


def test_kpi_meets_target():
    b = _bundle(target_value="10 ppm", target_direction="Lower is better")
    b["measurement"] = [{"m_date": "2026-01-01", "value": 40.0}, {"m_date": "2026-02-01", "value": 12.0}]
    assert not next(c for c in evaluate(b)["d"]["checks"] if c.id == "d.kpi_meets_target").passed
    b["measurement"].append({"m_date": "2026-03-01", "value": 9.0})
    assert next(c for c in evaluate(b)["d"]["checks"] if c.id == "d.kpi_meets_target").passed


def test_default_config_file_loads():
    from a3app.config import DEFAULT_PATH, load_config
    cfg = load_config(DEFAULT_PATH)
    assert cfg["a3_types"]["Basic"]["checks"]["a.is_is_not"] == "off"
