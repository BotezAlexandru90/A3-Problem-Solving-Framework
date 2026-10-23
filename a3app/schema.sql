CREATE TABLE IF NOT EXISTS a3 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Step A',

    -- General information
    title TEXT NOT NULL,
    topic_code TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    champion TEXT NOT NULL DEFAULT '',
    team_leader TEXT NOT NULL DEFAULT '',
    team_members TEXT NOT NULL DEFAULT '',
    a3_type TEXT NOT NULL DEFAULT 'Standard',
    trigger TEXT NOT NULL DEFAULT '',
    trigger_detail TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'Not assessed',
    customer_format_required TEXT NOT NULL DEFAULT 'Not checked',
    start_date TEXT NOT NULL DEFAULT '',
    deliverables TEXT NOT NULL DEFAULT '',
    scope_in TEXT NOT NULL DEFAULT '',
    scope_out TEXT NOT NULL DEFAULT '',

    -- Step A
    background TEXT NOT NULL DEFAULT '',
    symptom TEXT NOT NULL DEFAULT '',
    problem_statement TEXT NOT NULL DEFAULT '',
    expected_condition TEXT NOT NULL DEFAULT '',
    data_sources TEXT NOT NULL DEFAULT '',
    containment_exit_criteria TEXT NOT NULL DEFAULT '',
    containment_evidence TEXT NOT NULL DEFAULT '',
    early_warning_assessed TEXT NOT NULL DEFAULT 'Not assessed',
    early_warning_notes TEXT NOT NULL DEFAULT '',
    target_metric TEXT NOT NULL DEFAULT '',
    target_baseline TEXT NOT NULL DEFAULT '',
    target_value TEXT NOT NULL DEFAULT '',
    target_direction TEXT NOT NULL DEFAULT 'Lower is better',
    target_scope TEXT NOT NULL DEFAULT '',
    target_date TEXT NOT NULL DEFAULT '',

    -- Step B
    methods_used TEXT NOT NULL DEFAULT '',
    why_why TEXT NOT NULL DEFAULT '',
    detection_na_justification TEXT NOT NULL DEFAULT '',
    systemic_na_justification TEXT NOT NULL DEFAULT '',

    -- Step C
    solution_alternatives TEXT NOT NULL DEFAULT '',
    decision_rationale TEXT NOT NULL DEFAULT '',
    risks_side_effects TEXT NOT NULL DEFAULT '',

    -- Step D
    observed_result TEXT NOT NULL DEFAULT '',
    observation_window TEXT NOT NULL DEFAULT '',
    effect_evidence TEXT NOT NULL DEFAULT '',
    target_achieved TEXT NOT NULL DEFAULT 'Not assessed',
    deviation_acceptance TEXT NOT NULL DEFAULT '',
    recurrence_check TEXT NOT NULL DEFAULT '',
    containment_removed TEXT NOT NULL DEFAULT 'No',
    standardization TEXT NOT NULL DEFAULT '',
    process_owner TEXT NOT NULL DEFAULT '',
    lessons_learned_required TEXT NOT NULL DEFAULT 'Not assessed',
    lessons_learned_no_reason TEXT NOT NULL DEFAULT '',
    read_across_assessed TEXT NOT NULL DEFAULT 'No',
    champion_feedback TEXT NOT NULL DEFAULT '',
    closed_date TEXT NOT NULL DEFAULT '',
    is_template INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS is_is_not (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    is_value TEXT NOT NULL DEFAULT '',
    is_not_value TEXT NOT NULL DEFAULT '',
    difference TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS hypothesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    category TEXT NOT NULL DEFAULT 'Occurrence',
    hypothesis TEXT NOT NULL,
    fishbone TEXT NOT NULL DEFAULT '',
    reasoning TEXT NOT NULL DEFAULT '',
    verification_method TEXT NOT NULL DEFAULT '',
    expected_if_true TEXT NOT NULL DEFAULT '',
    actual_result TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Untested',
    owner TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS action (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    cause_id INTEGER REFERENCES hypothesis(id) ON DELETE SET NULL,
    owner TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Open',
    expected_result TEXT NOT NULL DEFAULT '',
    verification_evidence TEXT NOT NULL DEFAULT '',
    effectiveness TEXT NOT NULL DEFAULT 'Not assessed',
    completed_date TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS read_across (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    scope_item TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL DEFAULT '',
    owner TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Open',
    confirmation TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lesson (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    learning TEXT NOT NULL DEFAULT '',
    documented_where TEXT NOT NULL DEFAULT '',
    distribution TEXT NOT NULL DEFAULT '',
    standard_updated TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS why_step (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    cause_id INTEGER REFERENCES hypothesis(id) ON DELETE SET NULL,
    statement TEXT NOT NULL,
    seq INTEGER NOT NULL DEFAULT 1,
    evidence TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Unverified',
    is_root TEXT NOT NULL DEFAULT 'No'
);

CREATE TABLE IF NOT EXISTS measurement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    m_date TEXT NOT NULL,
    value REAL,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    user TEXT NOT NULL DEFAULT '',
    step TEXT NOT NULL DEFAULT '',
    entity TEXT NOT NULL,
    entity_id INTEGER,
    field TEXT NOT NULL DEFAULT '',
    old_value TEXT,
    new_value TEXT
);

CREATE TABLE IF NOT EXISTS signoff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a3_id INTEGER NOT NULL REFERENCES a3(id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    decision TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    user TEXT NOT NULL,
    ts TEXT NOT NULL,
    hist_mark INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_action_a3 ON action(a3_id);
CREATE INDEX IF NOT EXISTS ix_hyp_a3 ON hypothesis(a3_id);
CREATE INDEX IF NOT EXISTS ix_ra_a3 ON read_across(a3_id);
CREATE INDEX IF NOT EXISTS ix_lesson_a3 ON lesson(a3_id);
CREATE INDEX IF NOT EXISTS ix_iin_a3 ON is_is_not(a3_id);
CREATE INDEX IF NOT EXISTS ix_why_a3 ON why_step(a3_id);
CREATE INDEX IF NOT EXISTS ix_meas_a3 ON measurement(a3_id);
CREATE INDEX IF NOT EXISTS ix_hist_a3 ON history(a3_id, ts);
CREATE INDEX IF NOT EXISTS ix_signoff_a3 ON signoff(a3_id, step);
