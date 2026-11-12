import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import payment_client, mailer, reminders
from app.database import Base, engine

client = TestClient(app)


def admin_headers():
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(payment_client, "charge",
                        lambda amount, email: {"status": "success", "reference": "PAY-TEST"})


def make_event(**kw):
    body = {"name": "Hackathon", "price": 100, "capacity": 2, "venue": "Hall A", "date": "2026-12-01"}
    body.update(kw)
    return client.post("/events", json=body, headers=admin_headers()).json()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_list_events():
    make_event()
    r = client.get("/events")
    assert r.status_code == 200 and r.json()[0]["seats_left"] == 2


def test_search_events():
    make_event(name="Dance Battle")
    make_event(name="Coding Contest")
    assert len(client.get("/events", params={"q": "dance"}).json()) == 1


def test_register_returns_ticket_and_qr():
    ev = make_event()
    r = client.post("/register", json={"event_id": ev["id"], "student_name": "Asha", "student_email": "a@x.com"})
    assert r.status_code == 201
    code = r.json()["code"]
    qr = client.get(f"/tickets/{code}/qr.png")
    assert qr.status_code == 200 and qr.headers["content-type"] == "image/png"


def test_sold_out():
    ev = make_event(capacity=1)
    body = {"event_id": ev["id"], "student_name": "A", "student_email": "a@x.com"}
    assert client.post("/register", json=body).status_code == 201
    assert client.post("/register", json=body).status_code == 409


def test_payment_failure(monkeypatch):
    monkeypatch.setattr(payment_client, "charge", lambda a, e: {"status": "failed"})
    ev = make_event()
    r = client.post("/register", json={"event_id": ev["id"], "student_name": "A", "student_email": "a@x.com"})
    assert r.status_code == 402


def test_checkin_once_only():
    ev = make_event()
    code = client.post("/register", json={"event_id": ev["id"], "student_name": "A", "student_email": "a@x.com"}).json()["code"]
    assert client.post(f"/tickets/{code}/checkin", headers=admin_headers()).status_code == 200
    assert client.post(f"/tickets/{code}/checkin", headers=admin_headers()).status_code == 409


def test_admin_stats():
    ev = make_event()
    client.post("/register", json={"event_id": ev["id"], "student_name": "A", "student_email": "a@x.com"})
    s = client.get("/admin/stats", headers=admin_headers()).json()
    assert s["total_registrations"] == 1 and s["total_revenue"] == 100


def reg(ev, name="A", email="a@x.com"):
    return client.post("/register", json={"event_id": ev["id"], "student_name": name, "student_email": email}).json()


def test_login_wrong_password():
    r = client.post("/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_admin_routes_need_login():
    assert client.post("/events", json={"name": "X"}).status_code == 401
    assert client.get("/admin/stats").status_code == 401
    assert client.delete("/events/1").status_code == 401
    assert client.get("/admin/stats", headers={"Authorization": "Bearer fake.token"}).status_code == 401


def test_public_pages_need_no_login():
    assert client.get("/events").status_code == 200


def test_delete_event():
    ev = make_event()
    assert client.delete(f"/events/{ev['id']}", headers=admin_headers()).status_code == 204
    assert client.get("/events").json() == []


def test_manual_reminder_emails_only_not_checked_in(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda to, sub, body: sent.append(to) or "sent")
    ev = make_event(capacity=5)
    reg(ev, "A", "a@x.com")
    b = reg(ev, "B", "b@x.com")
    client.post(f"/tickets/{b['code']}/checkin", headers=admin_headers())
    r = client.post(f"/admin/events/{ev['id']}/remind", headers=admin_headers())
    assert r.json()["sent"] == 1 and sent == ["a@x.com"]


def test_auto_reminder_runs_once(monkeypatch):
    from datetime import date, timedelta
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda to, sub, body: sent.append(to) or "sent")
    ev = make_event(date=(date.today() + timedelta(days=1)).isoformat())
    reg(ev)
    reminders.run_auto_reminders()
    reminders.run_auto_reminders()  # second run must not email again
    assert sent == ["a@x.com"]


# ---------- team events ----------
def team_body(ev, team="Alpha", members=1):
    return {"event_id": ev["id"], "student_name": "Lead", "student_email": "lead@x.com", "team_name": team,
            "members": [{"name": f"M{i}", "email": f"m{i}@x.com"} for i in range(members)]}


def test_team_event_fields_returned():
    ev = make_event(min_team_size=2, max_team_size=4)
    assert ev["min_team_size"] == 2 and ev["max_team_size"] == 4
    assert make_event(name="Solo")["max_team_size"] == 1


def test_invalid_team_size_rejected():
    r = client.post("/events", json={"name": "X", "min_team_size": 3, "max_team_size": 2}, headers=admin_headers())
    assert r.status_code == 400
    r = client.post("/events", json={"name": "X", "min_team_size": 0, "max_team_size": 2}, headers=admin_headers())
    assert r.status_code == 400


def test_team_registration_uses_one_seat():
    ev = make_event(min_team_size=2, max_team_size=4, capacity=3)
    r = client.post("/register", json=team_body(ev, members=2))
    assert r.status_code == 201
    t = r.json()
    assert t["team_name"] == "Alpha" and t["team_size"] == 3 and len(t["members"]) == 2
    assert client.get("/events").json()[0]["seats_left"] == 2  # one team = one seat


def test_team_size_and_name_rules():
    ev = make_event(min_team_size=2, max_team_size=3)
    assert client.post("/register", json=team_body(ev, members=0)).status_code == 422   # too small
    assert client.post("/register", json=team_body(ev, members=3)).status_code == 422   # too big
    assert client.post("/register", json=team_body(ev, team="  ", members=1)).status_code == 422
    assert client.post("/register", json=team_body(ev, members=1)).status_code == 201


def test_individual_event_rejects_members():
    ev = make_event()
    assert client.post("/register", json=team_body(ev, members=1)).status_code == 422
    assert reg(ev)["team_size"] == 1


def test_stats_show_teams_not_participants():
    team_ev = make_event(name="Hack", min_team_size=2, max_team_size=4, capacity=5)
    solo_ev = make_event(name="Quiz", capacity=5)
    client.post("/register", json=team_body(team_ev, members=2))
    reg(solo_ev)
    s = client.get("/admin/stats", headers=admin_headers()).json()
    assert s["total_teams"] == 1 and s["total_individuals"] == 1 and s["total_people"] == 4
    hack = next(e for e in s["events"] if e["event"] == "Hack")
    assert hack["team_event"] is True and hack["registered"] == 1 and hack["people"] == 3


def test_registrations_list_has_team_details():
    ev = make_event(min_team_size=2, max_team_size=4)
    client.post("/register", json=team_body(ev, team="Zeta", members=2))
    row = client.get(f"/admin/events/{ev['id']}/registrations", headers=admin_headers()).json()[0]
    assert row["team_name"] == "Zeta" and row["team_size"] == 3 and len(row["members"]) == 2


def test_checkins_list_shows_holder_name():
    ev = make_event()
    t = reg(ev, "Asha", "asha@x.com")
    assert client.get("/admin/checkins").status_code == 401
    assert client.get("/admin/checkins", headers=admin_headers()).json()["count"] == 0
    client.post(f"/tickets/{t['code']}/checkin", headers=admin_headers())
    data = client.get("/admin/checkins", headers=admin_headers()).json()
    assert data["count"] == 1
    item = data["items"][0]
    assert item["name"] == "Asha" and item["event"] == "Hackathon" and item["checked_in_at"].endswith("Z")


def test_team_checkin_shows_team_name():
    ev = make_event(min_team_size=2, max_team_size=4)
    t = client.post("/register", json=team_body(ev, team="Zeta", members=2)).json()
    out = client.post(f"/tickets/{t['code']}/checkin", headers=admin_headers()).json()
    assert out["team_name"] == "Zeta" and out["checked_in_at"]
    item = client.get("/admin/checkins", headers=admin_headers()).json()["items"][0]
    assert item["team_name"] == "Zeta" and item["team_size"] == 3


def test_team_reminders_email_every_member_with_email(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda to, sub, body: sent.append(to) or "sent")
    ev = make_event(min_team_size=2, max_team_size=4)
    body = team_body(ev, members=2)
    body["members"][1]["email"] = ""   # one member gave no email
    client.post("/register", json=body)
    r = client.post(f"/admin/events/{ev['id']}/remind", headers=admin_headers())
    assert r.json()["sent"] == 2 and sorted(sent) == ["lead@x.com", "m0@x.com"]


def test_migrate_adds_new_columns_to_old_database(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from app import database
    old = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with old.begin() as c:
        c.execute(text("CREATE TABLE events (id INTEGER PRIMARY KEY, name VARCHAR, capacity INTEGER)"))
        c.execute(text("CREATE TABLE tickets (id INTEGER PRIMARY KEY, student_name VARCHAR)"))
        c.execute(text("INSERT INTO events (id, name, capacity) VALUES (1, 'Old event', 10)"))
    database.migrate(old)
    database.migrate(old)  # running twice must be safe
    insp = inspect(old)
    assert {"min_team_size", "max_team_size"} <= {c["name"] for c in insp.get_columns("events")}
    assert {"team_name", "members", "checked_in_at"} <= {c["name"] for c in insp.get_columns("tickets")}
    with old.begin() as c:
        assert c.execute(text("SELECT max_team_size FROM events")).scalar() == 1
