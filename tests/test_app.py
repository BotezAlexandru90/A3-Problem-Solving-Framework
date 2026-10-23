import io
import re
import zipfile

import pytest
from werkzeug.security import generate_password_hash

from a3app import create_app, db

PW = "correct-horse-1"


@pytest.fixture
def app(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.sqlite3"), "SECRET_KEY": "test"})
    with app.app_context():
        for name, role in [("admin", "admin"), ("champ", "champion"), ("mem", "member"), ("view", "viewer")]:
            db.create_user(name, name.title(), generate_password_hash(PW), role)
    return app


def _login(c, username):
    tok = _csrf(c, "/login")
    c.post("/login", data={"csrf": tok, "username": username, "password": PW})


@pytest.fixture
def client(app):
    with app.test_client() as c:
        _login(c, "admin")
        yield c


def _csrf(client, url="/"):
    html = client.get(url).get_data(as_text=True)
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


def _new(client, title="Housing crack rate above 50 ppm on line 3"):
    tok = _csrf(client)
    r = client.post("/a3/new", data={"csrf": tok, "title": title})
    return int(r.headers["Location"].split("/a3/")[1].split("?")[0]), tok


def test_login_required(app):
    with app.test_client() as c:
        assert c.get("/").status_code == 302
        _login(c, "admin")
        assert c.get("/").status_code == 200


def test_wrong_password_rejected(app):
    with app.test_client() as c:
        tok = _csrf(c, "/login")
        r = c.post("/login", data={"csrf": tok, "username": "admin", "password": "wrong"})
        assert "Invalid username or password" in r.get_data(as_text=True)
        assert c.get("/").status_code == 302


def test_viewer_cannot_edit(app, client):
    a3_id, _ = _new(client)
    with app.test_client() as c:
        _login(c, "view")
        tok = _csrf(c)
        r = c.post(f"/a3/{a3_id}/save", data={"csrf": tok, "tab": "a", "version": 1, "symptom": "x"})
        assert r.status_code == 403


def test_member_cannot_signoff_or_delete(app, client):
    a3_id, _ = _new(client)
    with app.test_client() as c:
        _login(c, "mem")
        tok = _csrf(c)
        assert c.post(f"/a3/{a3_id}/signoff", data={"csrf": tok, "step": "a", "decision": "Approved"}).status_code == 403
        assert c.post(f"/a3/{a3_id}/delete", data={"csrf": tok, "confirm_title": "x"}).status_code == 403


def test_signoff_blocked_while_gate_open(app, client):
    a3_id, _ = _new(client)
    with app.test_client() as c:
        _login(c, "champ")
        tok = _csrf(c)
        r = c.post(f"/a3/{a3_id}/signoff", data={"csrf": tok, "step": "a", "decision": "Approved"},
                   follow_redirects=True)
        assert "Cannot approve" in r.get_data(as_text=True)
        r = c.post(f"/a3/{a3_id}/signoff", data={"csrf": tok, "step": "a", "decision": "Rework required",
                                                  "comment": "Quantify the problem"}, follow_redirects=True)
        assert "Sign-off recorded" in r.get_data(as_text=True)


def test_history_records_changes(client):
    a3_id, tok = _new(client)
    client.post(f"/a3/{a3_id}/save", data={"csrf": tok, "tab": "a", "version": 1, "symptom": "Crack at rib"})
    html = client.get(f"/a3/{a3_id}/history").get_data(as_text=True)
    assert "Crack at rib" in html and "symptom" in html and "Admin" in html


def test_search(client):
    a3_id, tok = _new(client)
    client.post(f"/a3/{a3_id}/hypothesis/edit", data={"csrf": tok, "category": "Occurrence",
                                                       "hypothesis": "Mold temperature PN-4711 too low",
                                                       "status": "Untested"})
    html = client.get("/search?q=pn-4711").get_data(as_text=True)
    assert "<mark>PN-4711</mark>" in html


def test_duplicate_and_template(client):
    a3_id, tok = _new(client)
    client.post(f"/a3/{a3_id}/save", data={"csrf": tok, "tab": "general", "version": 1, "title": "T",
                                            "champion": "Dr. X"})
    client.post(f"/a3/{a3_id}/template", data={"csrf": tok, "version": 2})
    assert "Template: T" in client.get("/").get_data(as_text=True)
    r = client.post("/a3/new", data={"csrf": tok, "title": "From template", "template_id": str(a3_id)})
    new_id = int(r.headers["Location"].split("/a3/")[1].split("?")[0])
    assert 'value="Dr. X"' in client.get(f"/a3/{new_id}").get_data(as_text=True)


def test_import_marks_unverified(client):
    a3_id, tok = _new(client)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>Customer reported 120 ppm cracked '
                                        'housings in week 12.</w:t></w:r></w:p></w:body></w:document>')
    r = client.post(f"/a3/{a3_id}/import", data={"csrf": tok, "stage": "extract",
                                                  "file": (io.BytesIO(buf.getvalue()), "notes.docx")},
                    content_type="multipart/form-data")
    html = r.get_data(as_text=True)
    assert "120 ppm" in html and 'value="problem_statement" selected' in html
    client.post(f"/a3/{a3_id}/import", data={"csrf": tok, "stage": "apply", "version": 1,
                                              "s0": "Customer reported 120 ppm cracked housings in week 12.",
                                              "t0": "problem_statement"})
    html = client.get(f"/a3/{a3_id}?tab=a").get_data(as_text=True)
    assert "[UNVERIFIED IMPORT] Customer reported" in html
    assert "count as empty" in html


def test_kpi_chart_and_stats(client):
    a3_id, tok = _new(client)
    client.post(f"/a3/{a3_id}/save", data={"csrf": tok, "tab": "a", "version": 1, "target_baseline": "50 ppm",
                                            "target_value": "10 ppm", "target_direction": "Lower is better"})
    for d, v in [("2026-09-01", "40"), ("2026-10-01", "8")]:
        client.post(f"/a3/{a3_id}/measurement/edit", data={"csrf": tok, "m_date": d, "value": v, "tab": "d"})
    html = client.get(f"/a3/{a3_id}?tab=d").get_data(as_text=True)
    assert "<svg" in html and "meets target" in html
    assert client.get("/stats").status_code == 200


def test_post_without_csrf_rejected(client):
    assert client.post("/a3/new", data={"title": "x"}).status_code == 400


def test_create_and_view(client):
    a3_id, _ = _new(client)
    for tab in ("general", "a", "b", "c", "d"):
        r = client.get(f"/a3/{a3_id}?tab={tab}")
        assert r.status_code == 200
        assert "quality gate" in r.get_data(as_text=True)


def test_cannot_advance_with_open_gate(client):
    a3_id, tok = _new(client)
    client.post(f"/a3/{a3_id}/status", data={"csrf": tok, "status": "Step B", "version": 1})
    html = client.get(f"/a3/{a3_id}").get_data(as_text=True)
    assert "Status <b>Step A</b>" in html


def test_cannot_close_from_cancelled_shortcut(client):
    a3_id, tok = _new(client)
    client.post(f"/a3/{a3_id}/status", data={"csrf": tok, "status": "Cancelled", "version": 1})
    client.post(f"/a3/{a3_id}/status", data={"csrf": tok, "status": "Closed", "version": 2})
    assert "Status <b>Cancelled</b>" in client.get(f"/a3/{a3_id}").get_data(as_text=True)


def test_version_conflict(client):
    a3_id, tok = _new(client)
    data = {"csrf": tok, "tab": "a", "version": 1, "early_warning_assessed": "No"}
    client.post(f"/a3/{a3_id}/save", data=data)
    r = client.post(f"/a3/{a3_id}/save", data=data, follow_redirects=True)
    assert "changed by someone else" in r.get_data(as_text=True)


def test_invalid_select_rejected(client):
    a3_id, tok = _new(client)
    r = client.post(f"/a3/{a3_id}/save", data={"csrf": tok, "tab": "a", "version": 1,
                                                 "early_warning_assessed": "Maybe"}, follow_redirects=True)
    assert "Invalid value" in r.get_data(as_text=True)


def test_action_cannot_link_foreign_cause(client):
    a1, tok = _new(client)
    a2, _ = _new(client, "Other gap")
    client.post(f"/a3/{a1}/hypothesis/edit", data={"csrf": tok, "category": "Occurrence", "hypothesis": "H",
                                                    "status": "Verified"})
    r = client.post(f"/a3/{a2}/action/edit", data={
        "csrf": tok, "action_type": "Correction", "description": "Fix", "cause_id": "1",
        "status": "Open", "effectiveness": "Not assessed"}, follow_redirects=True)
    assert "does not belong" in r.get_data(as_text=True)


def test_exports(client):
    a3_id, _ = _new(client)
    assert client.get(f"/a3/{a3_id}/export.md").status_code == 200
    r = client.get(f"/a3/{a3_id}/export.xlsx")
    assert r.status_code == 200 and r.data[:2] == b"PK"
    assert client.get(f"/a3/{a3_id}/print").status_code == 200
    for url in ("/actions", "/lessons", "/read-across"):
        assert client.get(url).status_code == 200
