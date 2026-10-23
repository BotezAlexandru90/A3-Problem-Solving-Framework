"""Field definitions and option lists shared by forms, gates and exports."""

# Triggers, severities, fishbone categories and suggestion lists come from a3config.toml.
A3_TYPES = ["Basic", "Standard", "Extended"]
STATUSES = ["Step A", "Step B", "Step C", "Step D", "Closed", "Cancelled"]
YES_NO = ["Not assessed", "Yes", "No"]
CUSTOMER_FORMAT = ["Not checked", "Internal A3 sufficient", "8D required (CQTS)", "Other customer format required"]

IS_IS_NOT_DIMENSIONS = ["What", "Where", "When", "How big", "Who"]

HYPOTHESIS_CATEGORIES = ["Occurrence", "Detection / escape", "Systemic"]
HYPOTHESIS_STATUSES = ["Untested", "Prioritized for verification", "Verified", "Excluded", "Inconclusive"]

ACTION_TYPES = [
    "Containment", "Correction", "Technical corrective", "Systemic / preventive",
    "Validation", "Standardization",
]
ACTION_STATUSES = ["Open", "In progress", "Done", "Cancelled"]
EFFECTIVENESS = ["Not assessed", "Effective", "Not effective"]
RA_STATUSES = ["Open", "In progress", "Done", "Not applicable"]
DIRECTIONS = ["Lower is better", "Higher is better"]
WHY_STATUSES = ["Unverified", "Supported", "Not supported"]
WHY_ROOT = ["No", "Technical root cause", "Systemic root cause"]
SIGNOFF_DECISIONS = ["Approved", "Rework required"]

# (field, label, widget) — widget: text | area | date | select:<OPTIONS_NAME>
GENERAL_FIELDS = [
    ("title", "A3 title (problem / gap, no cause or solution)", "text"),
    ("topic_code", "Topic code", "list:topic_codes"),
    ("location", "Location", "list:locations"),
    ("department", "Department / organizational unit", "list:departments"),
    ("champion", "Champion", "text"),
    ("team_leader", "Team Leader", "text"),
    ("team_members", "Team members and functions", "area"),
    ("a3_type", "A3 type", "select:A3_TYPES"),
    ("trigger", "Trigger", "select:TRIGGERS"),
    ("trigger_detail", "Trigger detail / reference", "text"),
    ("severity", "Severity (as classified per applicable criteria)", "select:SEVERITIES"),
    ("customer_format_required", "Customer-specific format check", "select:CUSTOMER_FORMAT"),
    ("start_date", "Start date", "date"),
    ("deliverables", "Expected deliverables", "area"),
    ("scope_in", "In scope", "area"),
    ("scope_out", "Out of scope / exclusions", "area"),
]

STEP_A_FIELDS = [
    ("background", "History and background (what, how/when detected, what changed, sources)", "area"),
    ("symptom", "Symptom (directly observable)", "area"),
    ("problem_statement", "Problem description / current condition (what, where, when, how often, how big, population)", "area"),
    ("expected_condition", "Expected requirement / standard", "area"),
    ("data_sources", "Data sources for the above", "area"),
    ("containment_exit_criteria", "Containment exit criteria", "area"),
    ("containment_evidence", "Evidence that containment is working", "area"),
    ("early_warning_assessed", "Early Warning assessed?", "select:YES_NO"),
    ("early_warning_notes", "Early Warning decision and recipients", "area"),
    ("target_metric", "Target metric", "text"),
    ("target_baseline", "Baseline value", "text"),
    ("target_value", "Target value", "text"),
    ("target_direction", "Target direction", "select:DIRECTIONS"),
    ("target_scope", "Target population / scope", "text"),
    ("target_date", "Target date", "date"),
]

STEP_B_FIELDS = [
    ("methods_used", "Methods used (Is/Is Not, Fishbone, Why-Why, FTA, DOE, ...)", "area"),
    ("why_why", "Why-Why summary / notes (structured chain below)", "area"),
    ("detection_na_justification", "Justification if no detection/escape cause applies", "area"),
    ("systemic_na_justification", "Justification if no systemic cause applies", "area"),
]

STEP_C_FIELDS = [
    ("solution_alternatives", "Solution alternatives considered", "area"),
    ("decision_rationale", "Decision rationale (effectiveness, risk, effort, cost, feasibility)", "area"),
    ("risks_side_effects", "Risks and unintended side effects", "area"),
]

STEP_D_FIELDS = [
    ("observed_result", "Observed result vs. target", "area"),
    ("observation_window", "Observation window", "text"),
    ("effect_evidence", "Evidence of effectiveness", "area"),
    ("target_achieved", "Step A target achieved?", "select:YES_NO"),
    ("deviation_acceptance", "If not achieved: accepted deviation and by whom", "area"),
    ("recurrence_check", "Non-recurrence check (window, result)", "area"),
    ("containment_removed", "Containment removed?", "select:YES_NO"),
    ("standardization", "Standards / processes / rules changed", "area"),
    ("process_owner", "Process Owner / Rule Manager", "text"),
    ("read_across_assessed", "Read Across assessed?", "select:YES_NO"),
    ("lessons_learned_required", "New Lessons Learned item required?", "select:YES_NO"),
    ("lessons_learned_no_reason", "Reason if no Lessons Learned item", "area"),
    ("champion_feedback", "Champion feedback", "area"),
]

STEPS = [
    ("general", "General", GENERAL_FIELDS),
    ("a", "A - Describe the problem", STEP_A_FIELDS),
    ("b", "B - Identify the root cause", STEP_B_FIELDS),
    ("c", "C - Determine and implement the solution", STEP_C_FIELDS),
    ("d", "D - Validate, standardize, share", STEP_D_FIELDS),
]

ALL_A3_FIELDS = [f for _, _, fields in STEPS for f in fields]
EDITABLE_COLUMNS = {f[0] for f in ALL_A3_FIELDS}

CHILD_FIELDS = {
    "is_is_not": [
        ("dimension", "Dimension", "select:IS_IS_NOT_DIMENSIONS"),
        ("is_value", "Is", "area"),
        ("is_not_value", "Is Not", "area"),
        ("difference", "Differences / changes", "area"),
    ],
    "hypothesis": [
        ("category", "Cause category", "select:HYPOTHESIS_CATEGORIES"),
        ("hypothesis", "Hypothesis", "area"),
        ("fishbone", "Fishbone category", "select:FISHBONE"),
        ("reasoning", "Reasoning / observation", "area"),
        ("verification_method", "Verification method and required data", "area"),
        ("expected_if_true", "Expected result if true", "area"),
        ("actual_result", "Actual result", "area"),
        ("evidence", "Evidence / attachment reference", "area"),
        ("status", "Status", "select:HYPOTHESIS_STATUSES"),
        ("owner", "Owner", "text"),
        ("due_date", "Due date", "date"),
    ],
    "action": [
        ("action_type", "Action type", "select:ACTION_TYPES"),
        ("description", "Action", "area"),
        ("cause_id", "Linked root cause", "cause"),
        ("owner", "Responsible owner", "text"),
        ("due_date", "Due date", "date"),
        ("status", "Status", "select:ACTION_STATUSES"),
        ("expected_result", "Expected result / verification plan", "area"),
        ("verification_evidence", "Verification evidence", "area"),
        ("effectiveness", "Result", "select:EFFECTIVENESS"),
        ("completed_date", "Completed date", "date"),
    ],
    "read_across": [
        ("scope_item", "Similar product / process / location / unit", "text"),
        ("rationale", "Evidence defining Read Across scope", "area"),
        ("action", "Required action", "area"),
        ("owner", "Owner", "text"),
        ("due_date", "Due date", "date"),
        ("status", "Status", "select:RA_STATUSES"),
        ("confirmation", "Implementation confirmation", "area"),
    ],
    "why_step": [
        ("cause_id", "Starting cause (should be verified)", "cause"),
        ("statement", "Why? (answer)", "area"),
        ("seq", "Order in chain", "int"),
        ("evidence", "Evidence supporting this step", "area"),
        ("status", "Status", "select:WHY_STATUSES"),
        ("is_root", "Root cause reached?", "select:WHY_ROOT"),
    ],
    "measurement": [
        ("m_date", "Date", "date"),
        ("value", "Value", "number"),
        ("note", "Note / source", "text"),
    ],
    "lesson": [
        ("title", "Lesson title", "text"),
        ("context", "Context where reusable", "area"),
        ("learning", "Learning", "area"),
        ("documented_where", "Documented where", "text"),
        ("distribution", "Distribution", "text"),
        ("standard_updated", "Standard / process updated", "text"),
    ],
}

CHILD_LABELS = {
    "is_is_not": "Is / Is Not entry",
    "hypothesis": "Cause hypothesis",
    "action": "Action",
    "read_across": "Read Across item",
    "lesson": "Lessons Learned item",
    "why_step": "Why-Why step",
    "measurement": "KPI measurement",
}

# Required (main) field of each child table
CHILD_MAIN = {"is_is_not": "dimension", "hypothesis": "hypothesis", "action": "description",
              "read_across": "scope_item", "lesson": "title", "why_step": "statement", "measurement": "m_date"}

FIELD_STEP = {f[0]: step for step, _, fields in STEPS for f in fields}
ACTION_TYPE_STEP = {"Containment": "a", "Correction": "c", "Technical corrective": "c",
                    "Systemic / preventive": "c", "Validation": "d", "Standardization": "d"}
CHILD_STEP = {"is_is_not": "a", "hypothesis": "b", "why_step": "b", "read_across": "d", "lesson": "d",
              "measurement": "d"}

BASE_OPTIONS = {
    "A3_TYPES": A3_TYPES, "YES_NO": YES_NO, "CUSTOMER_FORMAT": CUSTOMER_FORMAT,
    "IS_IS_NOT_DIMENSIONS": IS_IS_NOT_DIMENSIONS, "HYPOTHESIS_CATEGORIES": HYPOTHESIS_CATEGORIES,
    "HYPOTHESIS_STATUSES": HYPOTHESIS_STATUSES, "ACTION_TYPES": ACTION_TYPES,
    "ACTION_STATUSES": ACTION_STATUSES, "EFFECTIVENESS": EFFECTIVENESS, "RA_STATUSES": RA_STATUSES,
    "DIRECTIONS": DIRECTIONS, "WHY_STATUSES": WHY_STATUSES, "WHY_ROOT": WHY_ROOT,
    "SIGNOFF_DECISIONS": SIGNOFF_DECISIONS,
}


def build_options(cfg):
    pick = cfg["picklists"]
    opts = dict(BASE_OPTIONS)
    opts.update(TRIGGERS=[""] + pick["triggers"], SEVERITIES=pick["severities"],
                FISHBONE=[""] + pick["fishbone_categories"], topic_codes=pick["topic_codes"],
                locations=pick["locations"], departments=pick["departments"])
    return opts
