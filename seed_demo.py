"""Load (or remove) demo A3s that showcase the tool.

python seed_demo.py              # add 25 demo A3s to ./instance/a3.sqlite3
python seed_demo.py --remove     # delete all demo A3s again
python seed_demo.py --data-dir PATH

All names, plants, parts and figures are fictional. Demo A3s use topic codes starting with "DEMO-".
"""
import argparse
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from a3app import db as a3db
from a3app import gates
from a3app.config import find_config, load_config

TODAY = date.today()
STAGES = ["A-early", "A", "B", "C", "D", "Closed"]  # plus "Cancelled"

CHAMPIONS = ["M. Weber", "A. Popescu", "J. Novak", "L. Schmidt"]
LEADERS = ["R. Ionescu", "K. Tanaka", "S. Mueller", "D. Rossi", "E. Varga", "P. Kowalski"]

# title, type, trigger, severity, department, location, product,
# symptom, metric, baseline, target, unit, direction,
# occurrence cause, detection cause (None = N/A), systemic cause, excluded hypothesis,
# containment, fix occurrence, fix detection, fix systemic, stage, days since start
S = [
    ("Solder voids on ECU power stage exceed IPC limit on SMT line 2", "Extended", "Customer request or complaint", "2",
     "Plant Operations", "Plant North", "Engine ECU E-200",
     "AXI images show voids >25 % under MOSFET thermal pads", "Units with void area >25 %", 4200, 500, "ppm", "Lower is better",
     "Reflow peak zone 6 set 8 degC below paste supplier window after oven maintenance",
     "AXI void threshold set to 35 % instead of 25 % in inspection program",
     "Oven maintenance checklist has no reflow profile re-verification step",
     "Contaminated solder paste lot (lot analysis within specification)",
     "100 % AXI re-inspection of stock and WIP at 25 % threshold",
     "Restore validated profile and lock oven recipe parameters", "Correct AXI threshold and add program checksum check",
     "Add profile re-verification and sign-off to oven maintenance checklist", "Closed", 320),
    ("Connector pin push-back on body controller harness interface", "Standard", "Warranty", "3",
     "Quality", "Plant South", "Body Controller BC-7",
     "Intermittent loss of door lock function, pin 14 pushed back in field returns",
     "Pin push-back returns per month", 18, 2, "returns", "Lower is better",
     "Terminal retention lance deformed by worn crimp tool insert",
     "Pin retention push test performed only at first-off, not per shift",
     "Tool wear limits not defined in maintenance plan for crimp inserts",
     "Harness routing strain at customer (no correlation with vehicle line)",
     "Push test of all connectors in stock before shipment",
     "Replace insert and introduce insert life counter", "Push test every 2 hours per shift with record",
     "Define tool wear limits for all crimp inserts in maintenance plan", "Closed", 290),
    ("Brake sensor signal dropouts in 0-mileage at customer plant", "Extended", "0-mileage", "1",
     "Plant Operations", "Plant East", "Wheel Speed Sensor WS-3",
     "Sensor signal lost during end-of-line roller test at customer", "0-mileage failures", 640, 50, "ppm", "Lower is better",
     "Overmold gate position causes knit line over sensor IC lead frame",
     "Leak test at EOL does not detect micro-cracks along knit line",
     "Design FMEA did not cover knit-line risk for new overmold geometry",
     "ESD damage during handling (no ESD signature in failure analysis)",
     "Customer line: 100 % signal check, our plant: X-ray of all lots since week 14",
     "Move overmold gate and validate with CT scan", "Add thermal shock + signal test on sample basis per lot",
     "Add knit-line failure mode to DFMEA catalogue for overmolded sensors", "D", 150),
    ("Display backlight flicker at low temperature (-30 degC)", "Standard", "R&D", "3",
     "R&D", "R&D Center West", "Cluster Display CD-12",
     "Visible flicker at -30 degC during climatic chamber validation", "Units flickering in cold test", 12, 0, "% of samples",
     "Lower is better",
     "LED driver PWM frequency drops below 200 Hz at low temperature due to oscillator tolerance",
     "Cold test in DV plan only at -20 degC instead of -30 degC requirement",
     "Requirement change (-30 degC) not propagated to test specification",
     "Backlight LED batch variation (two batches show same behaviour)",
     "Cold-start test added for all prototype builds",
     "Change oscillator component to tighter tolerance part", "Align DV test temperature to -30 degC",
     "Link requirement changes automatically to test specification review", "C", 95),
    ("Scrap rate of injection-molded housings above target on press 7", "Basic", "Improvement", "4",
     "Plant Operations", "Plant South", "Housing H-55",
     "Short shots and flash on housings from press 7", "Scrap rate press 7", 4.8, 1.5, "%", "Lower is better",
     "Hot runner nozzle 3 temperature controller drifts by 15 degC",
     None,
     "Hot runner controllers not part of preventive maintenance calibration plan",
     "Material moisture (dryer logs within limits)",
     "Visual 100 % check of press 7 output",
     "Replace controller of nozzle 3 and recalibrate all zones", None,
     "Add hot runner controllers to annual calibration plan", "Closed", 260),
    ("Late delivery of PCB assemblies from supplier S-114", "Standard", "Disruption", "3",
     "Supply Chain", "Plant North", "PCB assembly P-900",
     "Line stops due to missing PCB assemblies", "On-time delivery S-114", 82, 97, "%", "Higher is better",
     "Supplier capacity planning ignores our forecast updates",
     "Supplier delivery performance reviewed only quarterly",
     "No escalation rule for repeated late deliveries in supplier management process",
     "Customs delays (shipments cleared within 24 h)",
     "Safety stock increased to 5 days, daily call with supplier",
     "Weekly forecast EDI to supplier with confirmation", "Weekly OTD dashboard with threshold alarm",
     "Add escalation rule to supplier management process", "B", 40),
    ("Audit finding: ESD control not verified at rework stations", "Basic", "Audit", "3",
     "Quality", "Plant East", "All products (rework area)",
     "Audit found 3 of 6 rework stations without valid ESD check record", "Rework stations without valid ESD record", 3, 0,
     "stations", "Lower is better",
     "ESD wrist strap tester at rework area out of order since 2 months",
     "Daily ESD record checked by nobody (no reviewer defined)",
     "ESD control plan does not assign ownership for the rework area",
     "Operators not trained (all training records valid)",
     "Spare tester installed, all stations checked same day",
     "Repair tester and add second tester as backup", "Shift leader reviews ESD records daily",
     "Assign ESD ownership per area in ESD control plan", "Closed", 230),
    ("Software flashing failures at end-of-line tester 3", "Standard", "Team decision", "3",
     "Test Engineering", "Plant North", "Gateway ECU GW-4",
     "Flashing aborts with timeout on EOL tester 3", "Flashing failure rate EOL 3", 2.6, 0.3, "%", "Lower is better",
     "CAN bus termination resistor in test adapter degraded (95 ohm instead of 120 ohm)",
     "Adapter self-test does not measure bus termination",
     "Test adapter maintenance not covered by preventive maintenance system",
     "Software image corruption on server (checksums verified OK)",
     "Failed units re-flashed on tester 1 after root cause analysis",
     "Replace termination resistor and adapter cable", "Add termination measurement to adapter self-test",
     "Register test adapters in preventive maintenance system", "C", 75),
    ("Customer complaint: scratched lens surfaces on camera modules", "Standard", "Customer request or complaint", "2",
     "Quality", "Plant East", "Front Camera FC-2",
     "Scratches on lens visible in customer incoming inspection", "Complaint rate scratched lenses", 900, 50, "ppm",
     "Lower is better",
     "Lens cap removed too early at station 40 and lens touches tray separator",
     "Final visual inspection lighting angle does not reveal fine scratches",
     "Packaging change was released without handling risk review",
     "Scratches from customer handling (scratches found in our stock as well)",
     "Sorting of all stock with dark-field lighting, sorted parts labelled",
     "Move lens cap removal to station 60 after packaging", "Install dark-field lighting at final inspection",
     "Add handling risk review to packaging change process", "D", 120),
    ("Radar module calibration drift after thermal cycling", "Extended", "R&D", "2",
     "R&D", "R&D Center West", "Corner Radar CR-5",
     "Angular offset >0.5 deg after 500 thermal cycles", "Samples with offset >0.5 deg", 30, 0, "% of samples",
     "Lower is better",
     "Adhesive between radome and housing creeps above 85 degC",
     "Thermal cycling not part of calibration validation plan",
     "Material change process does not require re-validation of calibration",
     "Firmware temperature compensation bug (code review and HIL test OK)",
     "Prototype builds limited to 85 degC use",
     "Change to adhesive with higher glass transition temperature", "Add thermal cycling to calibration validation",
     "Require calibration re-validation for adhesive/material changes", "B", 55),
    ("Label mix-up: wrong part number labels on shipping boxes", "Basic", "Customer request or complaint", "2",
     "Logistics", "Plant South", "Seat Module SM-1 (two variants)",
     "Customer received boxes with variant B label containing variant A parts", "Mislabelled boxes", 4, 0, "boxes",
     "Lower is better",
     "Label printer queue not cleared at variant change, old labels printed",
     "Box label not scanned against part label before shipping",
     "Variant change procedure in logistics does not include printer queue reset",
     "Wrong parts packed by operator (parts and work order matched)",
     "All boxes in stock and in transit re-checked by scanning",
     "Automatic printer queue reset at variant change", "Scan check box label vs. part label at packing",
     "Update variant change procedure in logistics", "Closed", 210),
    ("Torque out of tolerance on housing screws at assembly cell 4", "Basic", "Team decision", "4",
     "Plant Operations", "Plant North", "Engine ECU E-200",
     "Torque monitoring shows NOK values on screw 3", "Torque NOK rate cell 4", 1.9, 0.2, "%", "Lower is better",
     "Screwdriver bit worn, cam-out at final torque",
     None,
     "Bit change interval defined by time, not by number of cycles",
     "Screw supplier change (screw dimensions in specification)",
     "NOK parts re-screwed and checked",
     "Change bits every 20,000 cycles via counter", None,
     "Cycle-based tool change intervals for all screwdrivers", "D", 85),
    ("Stop ship: missing conformal coating on airbag control units", "Extended", "Stop ship", "1",
     "Plant Operations", "Plant East", "Airbag Control Unit AC-9",
     "Coating missing on connector side of PCB found by customer audit", "Units without coating", 1200, 0, "ppm",
     "Lower is better",
     "Coating robot program for new PCB revision skipped connector area",
     "UV inspection camera mask still based on old PCB revision",
     "PCB revision change did not trigger coating program and inspection review",
     "Coating material viscosity out of range (QC records OK)",
     "Shipment stop, 100 % UV inspection of all units in stock and at customer",
     "Correct robot program and verify with coverage test", "Update UV inspection mask for all PCB revisions",
     "Link PCB revision changes to process program review checklist", "C", 30),
    ("High first-pass-yield loss at ICT on gateway ECU", "Standard", "Improvement", "4",
     "Test Engineering", "Plant North", "Gateway ECU GW-4",
     "ICT fails on capacitor tests without real defects", "ICT first pass yield", 93.5, 98.5, "%", "Higher is better",
     "Test probes contaminated with flux residue",
     "False failures not analysed separately from real defects",
     "No probe cleaning interval defined in ICT maintenance",
     "Capacitor supplier lot variation (values in tolerance)",
     "Failed boards re-tested once before repair",
     "Introduce probe cleaning every 5,000 cycles", "Separate false-call statistics in ICT reporting",
     "Define probe cleaning and replacement intervals", "B", 35),
    ("Moisture-sensitive components exceeded floor life in storage", "Basic", "Internal rule", "3",
     "Logistics", "Plant South", "MSL 3 components (BGA)",
     "Opened reels exceeded 168 h floor life before use", "Reels exceeding floor life", 14, 0, "reels per month",
     "Lower is better",
     "Opened reels returned to normal storage instead of dry cabinet",
     "Floor life tracked manually on paper labels",
     "MSD handling rule not reflected in warehouse work instruction",
     "Dry cabinet humidity failure (logs below 5 % RH)",
     "Affected reels baked per J-STD-033 before use",
     "", "", "", "A", 12),
    ("Warranty returns: CAN transceiver failures in telematics unit", "Extended", "Warranty", "2",
     "Quality", "Plant East", "Telematics Unit TU-8",
     "No CAN communication, transceiver damaged in failure analysis", "Warranty returns CAN failure", 85, 10, "ppm",
     "Lower is better",
     "", "", "", "", "Customer informed, failure analysis of all returns", "", "", "", "A", 9),
    ("Technical compliance: RoHS declaration missing for two purchased parts", "Basic", "Technical compliance", "3",
     "Purchasing", "Plant North", "Purchased parts 4711-A, 4712-B",
     "Compliance check found missing RoHS declarations", "Parts without declaration", 2, 0, "parts", "Lower is better",
     "", "", "", "", "", "", "", "", "Cancelled", 60),
    ("Unplanned downtime of pick-and-place line 5 above target", "Standard", "Management direction", "4",
     "Plant Operations", "Plant South", "SMT line 5",
     "Frequent nozzle-related stops on placement head 2", "Unplanned downtime line 5", 42, 15, "hours per month",
     "Lower is better",
     "Nozzle cleaning unit pressure set too low, clogged nozzles",
     "Downtime reasons recorded as 'other' in 60 % of stops",
     "Downtime reason codes not standardised across SMT lines",
     "Feeder quality (feeder calibration OK)",
     "Extra nozzle check at shift start",
     "Correct cleaning unit pressure and add pressure monitoring", "Mandatory reason code selection at line stop",
     "Standard downtime reason code catalogue for all SMT lines", "D", 110),
    ("Field returns: cracked ceramic capacitors near board edge", "Extended", "Warranty", "2",
     "Quality", "Plant North", "Power Module PM-6",
     "Short circuit due to flex cracks in 1206 MLCCs within 3 mm of board edge", "Field returns flex cracks", 120, 10, "ppm",
     "Lower is better",
     "Depaneling router fixture causes board bending >1,000 microstrain",
     "No strain gauge measurement after fixture changes",
     "Design rules allow large MLCCs within 3 mm of breakaway edge",
     "Thermal shock in vehicle (failure pattern only near board edge)",
     "Electrical test with elevated voltage on all units in stock",
     "Redesign depaneling fixture support points", "Strain gauge test after every fixture change",
     "Update PCB design rule: no MLCC >0805 within 5 mm of board edge", "Closed", 340),
    ("Incorrect variant coding in seat control module at EOL", "Standard", "0-mileage", "2",
     "Test Engineering", "Plant South", "Seat Module SM-1",
     "Modules coded as heated-seat variant without heating hardware", "Wrong coding at customer", 300, 0, "ppm",
     "Lower is better",
     "EOL coding table not updated for new variant number",
     "EOL readback compares coding against the same wrong table",
     "Variant release process has no step for EOL coding table update",
     "Operator selected wrong variant (selection is automatic via scan)",
     "All modules in stock re-coded and verified",
     "Update coding table", "Readback against independent BOM data", "Add EOL table update to variant release",
     "B", 28),
    ("Delayed requirement changes reaching test team in R&D project X", "Standard", "R&D", "4",
     "R&D", "R&D Center West", "Project X (domain controller)",
     "Tests executed against outdated requirements in 3 sprints", "Requirement changes reaching test within 5 days", 40,
     95, "%", "Higher is better",
     "Requirement tool notifications go to a mailbox nobody reads",
     "Test review does not check requirement baseline version",
     "Change management process lacks a defined interface to test planning",
     "Test team capacity shortage (tests were done, but on old baseline)",
     "Weekly manual comparison of requirement baseline vs. test plan",
     "Route notifications to test leads with acknowledgement", "Check baseline version in test review checklist",
     "Define change-to-test interface in change management process", "C", 70),
    ("Customer 8D responses exceed 10-day deadline", "Basic", "Organizational trigger matrix", "3",
     "Quality", "Plant North", "Customer complaint process",
     "8D D3-D4 responses sent late", "8D responses within 10 days", 55, 95, "%", "Higher is better",
     "", "", "", "", "", "", "", "", "A-early", 4),
    ("Noise (buzzing) from HVAC actuator at low speed", "Standard", "Customer request or complaint", "Not assessed",
     "Quality", "Plant East", "HVAC Actuator HA-3",
     "Customer reports buzzing noise at low motor speed", "Noise complaints", 0, 0, "", "Lower is better",
     "", "", "", "", "", "", "", "", "A-early", 2),
]

TEMPLATES = [
    ("TEMPLATE - Customer complaint (Standard A3)", "Standard", "Customer request or complaint", {
        "scope_in": "[[Affected product / part numbers / customer / plant]]",
        "scope_out": "[[Explicitly excluded products, plants or failure modes]]",
        "background": "[[What happened? How and when was it detected? Reference CQTS number. What changed before?]]",
        "symptom": "[[What does the customer observe?]]",
        "problem_statement": "[[What / where / when / how many / how big - quantified, no cause, no solution]]",
        "expected_condition": "[[Requirement or specification that is not met]]",
        "data_sources": "[[CQTS, SAP CBW, failure analysis report, ...]]",
        "containment_exit_criteria": "[[When can the containment be removed?]]",
        "target_metric": "[[e.g. complaint rate in ppm]]",
    }),
    ("TEMPLATE - Basic A3 for line issues", "Basic", "Team decision", {
        "scope_in": "[[Line / station / product]]",
        "scope_out": "[[Not in scope]]",
        "background": "[[What happened on the line, since when?]]",
        "symptom": "[[Observed defect or stop]]",
        "problem_statement": "[[Quantified gap: rate, downtime, scrap ...]]",
        "target_metric": "[[e.g. scrap rate %]]",
    }),
]


class Seeder:
    def __init__(self, con):
        self.con = con

    def ts(self, d, hour=9):
        return datetime.combine(d, datetime.min.time()).replace(hour=hour).isoformat(timespec="seconds")

    def hist(self, a3_id, when, user, step, entity, entity_id, field, old, new):
        cur = self.con.execute(
            "INSERT INTO history (a3_id, ts, user, step, entity, entity_id, field, old_value, new_value) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (a3_id, when, user, step, entity, entity_id, field, old, new))
        return cur.lastrowid

    def insert(self, table, values):
        cols = ", ".join(values)
        cur = self.con.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(values))})",
                               list(values.values()))
        return cur.lastrowid

    def signoff(self, a3_id, step, when, champion, decision="Approved", comment=""):
        mark = self.con.execute("SELECT COALESCE(MAX(id), 0) FROM history WHERE a3_id = ?", (a3_id,)).fetchone()[0]
        self.insert("signoff", {"a3_id": a3_id, "step": step, "decision": decision, "comment": comment,
                                "user": champion, "ts": when, "hist_mark": mark})
        self.hist(a3_id, when, champion, "", "signoff", None, f"sign-off {step.upper()}", None,
                  f"{decision}: {comment}")


def build(seeder, idx, sc):
    (title, typ, trig, sev, dept, loc, prod, sym, metric, base, target, unit, direction,
     occ, det, sysc, excl, cont, fix_occ, fix_det, fix_sys, stage, age) = sc
    con = seeder.con
    champ, tl = CHAMPIONS[idx % len(CHAMPIONS)], LEADERS[idx % len(LEADERS)]
    member = LEADERS[(idx + 2) % len(LEADERS)]
    start = TODAY - timedelta(days=age)
    stage_i = 6 if stage == "Cancelled" else STAGES.index(stage)
    lvl = 0 if stage == "Cancelled" else stage_i  # 0 A-early, 1 in A, 2 in B, 3 in C, 4 in D, 5 closed
    high = sev in ("1", "2")
    fmt = lambda v: f"{v:g} {unit}".strip()  # noqa: E731

    # Step durations (days) to build a plausible timeline
    dur = {"A": max(3, age // 8), "B": max(5, age // 6), "C": max(7, age // 5), "D": max(10, age // 4)}
    when = {"A": start}
    for prev, nxt in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "Closed")):
        when[nxt] = when[prev] + timedelta(days=dur[prev])
    if stage == "Closed":
        when["Closed"] = min(when["Closed"], TODAY - timedelta(days=5))

    a3 = {
        "title": title, "topic_code": f"DEMO-{idx + 1:02d}", "location": loc, "department": dept,
        "champion": champ if lvl >= 1 or stage == "Cancelled" else "", "team_leader": tl,
        "team_members": f"{tl} (lead, {dept})\n{member} (Quality)\nT. Horvat (Process engineering)\nN. Silva (Production)"
        if lvl >= 1 else "",
        "a3_type": typ, "trigger": trig, "trigger_detail": f"Ref. DEMO-{1000 + idx}",
        "severity": sev, "start_date": start.isoformat(),
        "customer_format_required": ("8D required (CQTS)" if idx == 8 else "Internal A3 sufficient")
        if trig == "Customer request or complaint" and lvl >= 1 else "Not checked",
        "deliverables": "Verified root causes, effective corrective actions, updated standards" if lvl >= 1 else "",
        "scope_in": f"{prod} at {loc}" if lvl >= 1 else "",
        "scope_out": "Other products and plants (covered by Read Across)" if lvl >= 1 else "",
        "background": f"{sym}. Detected {start.strftime('%d %b %Y')} via {trig.lower()}. "
                      f"Affected product: {prod} at {loc}.",
        "symptom": sym,
        "is_template": 0,
    }
    if lvl >= 1:
        a3.update({
            "problem_statement": f"{metric} at {fmt(base)} for {prod} at {loc} since "
                                 f"{(start - timedelta(days=21)).isoformat()}; requirement is {fmt(target)} or better.",
            "expected_condition": f"{metric}: {fmt(target)} (specification / internal target)",
            "data_sources": "CQTS, SAP CBW production data, line MES records, failure analysis reports",
            "containment_exit_criteria": "Remove after corrective actions are validated as effective over 4 weeks",
            "containment_evidence": "Containment checks since start found and blocked all suspect units; "
                                    "no further escapes reported",
            "early_warning_assessed": "Yes" if high else "No",
            "early_warning_notes": "Early Warning sent to sister plants and BA quality; customer informed"
            if high else "Not required (severity 3/4); local team informed",
            "target_metric": metric, "target_baseline": fmt(base), "target_value": fmt(target),
            "target_direction": direction, "target_scope": f"{prod}, {loc}",
            "target_date": (when["A"] + timedelta(days=max(60, age))).isoformat(),
        })
    if lvl == 1:  # in Step A: leave typical gaps
        a3["target_value"] = ""
        a3["data_sources"] = ""
    if lvl >= 2:
        a3.update({
            "methods_used": "Is / Is Not, Fishbone, Why-Why, failure analysis, trial runs",
            "why_why": "See structured Why-Why chain.",
            "detection_na_justification": "" if det else "No detection step exists for this failure mode; "
                                                         "covered by occurrence and systemic actions.",
        })
    if lvl >= 3:
        a3.update({
            "solution_alternatives": "1) Selected fix\n2) Additional inspection only (rejected: does not remove cause)\n"
                                     "3) Supplier/design change (rejected: lead time)",
            "decision_rationale": "Selected solutions remove the verified causes with lowest risk and effort.",
            "risks_side_effects": "" if (lvl == 3 and idx % 2 == 0) else
            "Trial run confirmed no side effects on cycle time or other characteristics.",
        })
    if lvl >= 4:
        a3.update({
            "observed_result": f"{metric} reduced from {fmt(base)} to target level",
            "observation_window": "8 weeks after implementation",
            "effect_evidence": "KPI trend (see measurements), CQTS, monthly quality report",
            "recurrence_check": "No recurrence within the observation window",
            "standardization": f"Updated: {fix_sys or 'process standard'}; control plan and work instructions revised",
            "process_owner": "Process Owner Quality Management",
        })
    if stage == "Closed":
        a3.update({
            "target_achieved": "Yes", "containment_removed": "Yes", "read_across_assessed": "Yes",
            "lessons_learned_required": "Yes" if idx % 4 else "No",
            "lessons_learned_no_reason": "" if idx % 4 else "Learning already covered by existing Lessons Learned item",
            "champion_feedback": "Good fact-based work, root causes verified and standards updated.",
            "closed_date": when["Closed"].isoformat(),
        })

    status = {0: "Step A", 1: "Step A", 2: "Step B", 3: "Step C", 4: "Step D", 5: "Closed", 6: "Cancelled"}[stage_i]
    created = seeder.ts(start)
    a3.update(status=status, created_at=created, updated_at=seeder.ts(TODAY - timedelta(days=1)),
              updated_by=tl, version=1)
    a3_id = seeder.insert("a3", a3)
    seeder.hist(a3_id, created, tl, "general", "a3", a3_id, "(created)", None, title)

    def child(table, values, step):
        values["a3_id"] = a3_id
        rid = seeder.insert(table, values)
        seeder.hist(a3_id, created, tl, step, table, rid, "(created)", None, None)
        return rid

    due = lambda d: (when["A"] + timedelta(days=d)).isoformat()  # noqa: E731
    containment_done = lvl >= 4
    if cont:
        child("action", {"action_type": "Containment", "description": cont, "owner": tl, "due_date": due(3),
                         "status": "Done" if containment_done else "In progress",
                         "expected_result": "No suspect units reach the customer",
                         "verification_evidence": "Sorting records" if lvl >= 2 else "",
                         "effectiveness": "Effective" if containment_done else "Not assessed",
                         "completed_date": due(40) if containment_done else ""}, "a")

    if lvl >= 1 and typ != "Basic":
        for dim, is_v, not_v, diff in [
            ("What", sym, "Other failure modes on the same product", "Only this failure mode"),
            ("Where", f"{loc}, {prod}", "Other plants building similar products", "Plant-specific process"),
            ("When", f"Since {(start - timedelta(days=21)).isoformat()}", "Before that date", "Change before start"),
            ("How big", fmt(base), "Target level " + fmt(target), "Gap to close"),
        ]:
            child("is_is_not", {"dimension": dim, "is_value": is_v, "is_not_value": not_v, "difference": diff}, "a")

    if lvl < 2:
        return a3_id, stage_i

    # Step B: hypotheses and Why-Why
    b_done = lvl >= 3
    st = (lambda s: s) if b_done else (lambda s: "Prioritized for verification" if s == "Verified" else "Untested")
    h_occ = child("hypothesis", {"category": "Occurrence", "hypothesis": occ, "fishbone": "Machine" if idx % 2 else "Method",
                                 "reasoning": "Change in timeline matches start of failures",
                                 "verification_method": "Reproduce with old/new setting (A/B trial)",
                                 "expected_if_true": "Failure reproducible with suspected setting",
                                 "actual_result": "Reproduced 8/8 with suspected setting, 0/8 with corrected" if b_done else "",
                                 "evidence": f"Trial report TR-{idx:02d}-01" if b_done else "",
                                 "status": st("Verified"), "owner": member, "due_date": due(20)}, "b")
    h_det = None
    if det:
        h_det = child("hypothesis", {"category": "Detection / escape", "hypothesis": det, "fishbone": "Measurement",
                                     "reasoning": "Defective parts passed all inspections",
                                     "verification_method": "Run known-bad samples through inspection",
                                     "expected_if_true": "Known-bad samples pass", "actual_result":
                                     "5/5 known-bad samples passed" if b_done else "",
                                     "evidence": f"Inspection test report TR-{idx:02d}-02" if b_done else "",
                                     "status": st("Verified"), "owner": tl, "due_date": due(22)}, "b")
    h_sys = child("hypothesis", {"category": "Systemic", "hypothesis": sysc, "fishbone": "Management",
                                 "reasoning": "Why did the process allow the change without control?",
                                 "verification_method": "Process and document review with process owner",
                                 "expected_if_true": "No requirement found in the standard",
                                 "actual_result": "Confirmed in process review" if b_done else "",
                                 "evidence": f"Review minutes MIN-{idx:02d}" if b_done else "",
                                 "status": st("Verified") if b_done else "Untested", "owner": tl, "due_date": due(25)},
                  "b")
    child("hypothesis", {"category": "Occurrence", "hypothesis": excl, "fishbone": "Material",
                         "reasoning": "Material lot change in the same period",
                         "verification_method": "Lot analysis and comparison", "expected_if_true": "Lot deviation found",
                         "actual_result": "No deviation found", "evidence": f"Lab report LR-{idx:02d}",
                         "status": "Excluded", "owner": member, "due_date": due(15)}, "b")
    if b_done or typ == "Extended":
        child("why_step", {"cause_id": h_occ, "statement": occ, "seq": 1, "evidence": f"TR-{idx:02d}-01",
                           "status": "Supported", "is_root": "Technical root cause"}, "b")
        child("why_step", {"cause_id": h_occ, "statement": sysc, "seq": 2, "evidence": f"MIN-{idx:02d}",
                           "status": "Supported" if b_done else "Unverified",
                           "is_root": "Systemic root cause" if b_done else "No"}, "b")

    if lvl < 3:
        return a3_id, stage_i

    # Step C: corrective actions
    c_done = lvl >= 4
    closed = stage == "Closed"
    overdue = (TODAY - timedelta(days=10)).isoformat()
    plans = [("Technical corrective", fix_occ, h_occ), ("Technical corrective", fix_det, h_det),
             ("Systemic / preventive", fix_sys, h_sys)]
    for n, (atype, text, cause) in enumerate(plans):
        if not text or cause is None:
            continue
        if c_done:
            status, eff = "Done", ("Effective" if closed or n == 0 else "Not assessed")
        else:
            status, eff = ("In progress", "Not assessed") if n == 0 else ("Open", "Not assessed")
        child("action", {"action_type": atype, "description": text, "cause_id": cause,
                         "owner": [member, tl, champ][n], "due_date": overdue if (not c_done and n == 1) else due(45 + 10 * n),
                         "status": status, "expected_result": f"{metric} at or better than {fmt(target)}",
                         "verification_evidence": f"Validation report VR-{idx:02d}-{n}" if c_done else "",
                         "effectiveness": eff, "completed_date": due(50 + 10 * n) if c_done else ""}, "c")

    if lvl < 4:
        return a3_id, stage_i

    # Step D: measurements, validation, Read Across, Lessons Learned
    m_start = when["C"]
    m_end = when["Closed"] if closed else TODAY
    points = max(4, min(10, (m_end - m_start).days // 14))
    for k in range(points):
        frac = k / (points - 1)
        d = m_start + (m_end - m_start) * frac
        if closed:
            val = base + (target - base) * min(1.0, frac * 1.25)
            val = val * 0.9 if (direction == "Lower is better" and frac > 0.8) else val
        else:
            val = base + (target - base) * frac * 0.85
        child("measurement", {"m_date": d.isoformat(), "value": round(val, 2), "note": "Monthly quality report"}, "d")
    child("action", {"action_type": "Validation", "description": f"Confirm {metric} over 8 weeks",
                     "owner": tl, "due_date": (m_end - timedelta(days=2)).isoformat(),
                     "status": "Done" if closed else "In progress", "expected_result": fmt(target),
                     "verification_evidence": "KPI trend in A3" if closed else "",
                     "effectiveness": "Effective" if closed else "Not assessed",
                     "completed_date": m_end.isoformat() if closed else ""}, "d")
    child("read_across", {"scope_item": f"Similar products to {prod} in other plants",
                          "rationale": "Same process / design rule used", "action": f"Check and apply: {fix_sys}",
                          "owner": champ, "due_date": (m_end - timedelta(days=5)).isoformat(),
                          "status": "Done" if closed else "Open",
                          "confirmation": "Confirmed by plant quality managers" if closed else ""}, "d")
    if closed and idx % 4:
        child("lesson", {"title": f"Lesson: {sysc[:60]}", "context": f"{dept}, {prod} and similar processes",
                         "learning": f"{occ}. Prevent by: {fix_sys}.", "documented_where": "Lessons Learned Database",
                         "distribution": "Quality network, process owners", "standard_updated": fix_sys}, "d")
    return a3_id, stage_i


def timeline(seeder, a3_id, sc, stage_i):
    """Status changes and Champion sign-offs with back-dated timestamps."""
    stage, age = sc[21], sc[22]
    champ = CHAMPIONS[S.index(sc) % len(CHAMPIONS)]
    tl = LEADERS[S.index(sc) % len(LEADERS)]
    start = TODAY - timedelta(days=age)
    dur = {"A": max(3, age // 8), "B": max(5, age // 6), "C": max(7, age // 5), "D": max(10, age // 4)}
    t = start
    prev = "Step A"
    for i, (step_key, nxt) in enumerate((("a", "Step B"), ("b", "Step C"), ("c", "Step D"), ("d", "Closed"))):
        if stage == "Cancelled" or stage_i < i + 2:
            break
        t = t + timedelta(days=dur[step_key.upper()])
        if stage == "Closed" and nxt == "Closed":
            t = min(t, TODAY - timedelta(days=5))
        if step_key == "b" and S.index(sc) % 5 == 0:
            seeder.signoff(a3_id, step_key, seeder.ts(t - timedelta(days=2), 10), champ, "Rework required",
                           "Detection cause not yet verified - please add test evidence.")
        seeder.signoff(a3_id, step_key, seeder.ts(t, 11), champ)
        seeder.hist(a3_id, seeder.ts(t, 12), tl, "", "a3", a3_id, "status", prev, nxt)
        prev = nxt
    if stage == "Cancelled":
        seeder.hist(a3_id, seeder.ts(start + timedelta(days=20), 12), tl, "", "a3", a3_id, "status", "Step A", "Cancelled")


def load_bundle(con, a3_id):
    b = {"a3": dict(con.execute("SELECT * FROM a3 WHERE id = ?", (a3_id,)).fetchone())}
    for table in a3db.CHILD_TABLES:
        b[table] = [dict(r) for r in con.execute(f"SELECT * FROM {table} WHERE a3_id = ? ORDER BY id", (a3_id,))]
    return b


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default=str(Path(__file__).parent / "instance"))
    p.add_argument("--remove", action="store_true", help="delete all demo A3s (topic code DEMO-*)")
    args = p.parse_args()
    path = Path(args.data_dir) / "a3.sqlite3"
    a3db.init_db(str(path))
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    demo_ids = [r[0] for r in con.execute("SELECT id FROM a3 WHERE topic_code LIKE 'DEMO-%'")]

    if args.remove:
        for i in demo_ids:
            con.execute("DELETE FROM history WHERE a3_id = ?", (i,))
            con.execute("DELETE FROM a3 WHERE id = ?", (i,))
        con.commit()
        print(f"Removed {len(demo_ids)} demo A3s from {path}.")
        return
    if demo_ids:
        sys.exit(f"{len(demo_ids)} demo A3s already exist in {path}. Run with --remove first.")

    seeder = Seeder(con)
    created = []
    for idx, sc in enumerate(S):
        a3_id, stage_i = build(seeder, idx, sc)
        timeline(seeder, a3_id, sc, stage_i)
        created.append((a3_id, sc, stage_i))
    for n, (title, typ, trig, fields) in enumerate(TEMPLATES):
        ts = seeder.ts(TODAY - timedelta(days=200 + n))
        values = {"title": title, "topic_code": f"DEMO-T{n + 1}", "a3_type": typ, "trigger": trig, "is_template": 1,
                  "created_at": ts, "updated_at": ts, "updated_by": "M. Weber", "start_date": ts[:10]}
        values.update(fields)
        tid = seeder.insert("a3", values)
        seeder.hist(tid, ts, "M. Weber", "general", "a3", tid, "(created)", None, title)
    con.commit()

    # Consistency check: every step before the current status must pass its gate.
    cfg = load_config(find_config(args.data_dir))
    problems = 0
    for a3_id, sc, stage_i in created:
        ev = gates.evaluate(load_bundle(con, a3_id), cfg)
        must = {2: ["general", "a"], 3: ["general", "a", "b"], 4: ["general", "a", "b", "c"],
                5: ["general", "a", "b", "c", "d"]}.get(stage_i, [])
        if sc[21] == "Cancelled":
            must = []
        for step in must:
            if not ev[step]["ready"]:
                problems += 1
                failed = [c.id for c in ev[step]["checks"] if not c.passed and c.level == "required"]
                print(f"WARNING A3 #{a3_id} ({sc[21]}): gate {step} open: {failed}")
    print(f"Added {len(created)} demo A3s and {len(TEMPLATES)} templates to {path}"
          + ("" if not problems else f" ({problems} consistency warnings)"))


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    main()
