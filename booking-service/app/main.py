import asyncio
import io
import json
from datetime import datetime
from contextlib import asynccontextmanager
import qrcode
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas, payment_client, auth, reminders
from .database import Base, engine, get_db, SessionLocal, migrate

Base.metadata.create_all(bind=engine)
migrate()

SEED_EVENTS = [
    dict(name="Hackathon 24h", description="Build something in a day",
         venue="CS Block", date="2026-12-05", price=100, capacity=60,
         min_team_size=2, max_team_size=4),
    dict(name="Battle of Bands", description="Live music finals",
         venue="Open Air Theatre", date="2026-12-06", price=150, capacity=300),
    dict(name="Tech Quiz", description="Team quiz on tech trivia",
         venue="Seminar Hall", date="2026-12-05", price=0, capacity=80,
         min_team_size=2, max_team_size=3),
]


@asynccontextmanager
async def lifespan(_app):
    db = SessionLocal()
    try:
        if db.query(models.Event).count() == 0:
            db.add_all([models.Event(**e) for e in SEED_EVENTS])
            db.commit()
    finally:
        db.close()
    task = asyncio.create_task(reminders.reminder_loop())
    yield
    task.cancel()


app = FastAPI(title="College Fest Booking Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _event_out(ev: models.Event, db: Session) -> schemas.EventOut:
    sold = db.query(func.count(models.Ticket.id)).filter(models.Ticket.event_id == ev.id).scalar()
    return schemas.EventOut(
        id=ev.id, name=ev.name, description=ev.description, venue=ev.venue,
        date=ev.date, price=ev.price, capacity=ev.capacity, seats_left=ev.capacity - sold,
        min_team_size=ev.min_team_size or 1, max_team_size=ev.max_team_size or 1,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/events", response_model=list[schemas.EventOut])
def list_events(q: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Event)
    if q:
        query = query.filter(models.Event.name.ilike(f"%{q}%"))
    return [_event_out(e, db) for e in query.all()]


@app.post("/auth/login")
def login(data: schemas.LoginIn):
    if not auth.check_credentials(data.username, data.password):
        raise HTTPException(401, "Wrong username or password")
    return {"token": auth.create_token(data.username)}


@app.post("/events", response_model=schemas.EventOut, status_code=201,
          dependencies=[Depends(auth.require_admin)])
def create_event(data: schemas.EventCreate, db: Session = Depends(get_db)):
    if data.min_team_size < 1 or data.max_team_size < data.min_team_size:
        raise HTTPException(400, "Team size is invalid: minimum must be at least 1 and not more than the maximum")
    if data.max_team_size > 20:
        raise HTTPException(400, "Maximum team size is 20")
    if data.capacity < 1:
        raise HTTPException(400, "Capacity must be at least 1")
    ev = models.Event(**data.model_dump())
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return _event_out(ev, db)


@app.delete("/events/{event_id}", status_code=204, dependencies=[Depends(auth.require_admin)])
def delete_event(event_id: int, db: Session = Depends(get_db)):
    ev = db.get(models.Event, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    db.delete(ev)
    db.commit()


@app.post("/register", response_model=schemas.TicketOut, status_code=201)
def register(data: schemas.RegisterIn, db: Session = Depends(get_db)):
    ev = db.get(models.Event, data.event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    if _event_out(ev, db).seats_left <= 0:
        raise HTTPException(409, "Event is sold out")

    max_size, min_size = ev.max_team_size or 1, ev.min_team_size or 1
    members = [{"name": m.name.strip(), "email": m.email.strip()} for m in data.members]
    team_name = data.team_name.strip()
    if max_size > 1:
        if not team_name:
            raise HTTPException(422, "Team name is required for this event")
        if any(not m["name"] for m in members):
            raise HTTPException(422, "Every team member needs a name")
        if not (min_size <= 1 + len(members) <= max_size):
            raise HTTPException(422, f"Team size must be between {min_size} and {max_size} members (including you)")
    elif members:
        raise HTTPException(422, "This event is for individual participants only")

    try:
        result = payment_client.charge(ev.price, data.student_email)
    except Exception:
        raise HTTPException(502, "Payment service unavailable")
    if result.get("status") != "success":
        raise HTTPException(402, "Payment failed")

    ticket = models.Ticket(
        event_id=ev.id, student_name=data.student_name,
        student_email=data.student_email, payment_ref=result.get("reference"),
        team_name=team_name if max_size > 1 else None,
        members=json.dumps(members) if members else None,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return _ticket_out(ticket)


def _members(t: models.Ticket) -> list:
    try:
        return json.loads(t.members) if t.members else []
    except ValueError:
        return []


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None  # stored in UTC


def _ticket_out(t: models.Ticket) -> schemas.TicketOut:
    members = _members(t)
    return schemas.TicketOut(
        code=t.code, event_id=t.event_id, event_name=t.event.name,
        student_name=t.student_name, student_email=t.student_email,
        checked_in=bool(t.checked_in), team_name=t.team_name or "",
        members=[schemas.Member(**m) for m in members], team_size=1 + len(members),
        checked_in_at=_iso(t.checked_in_at),
    )


@app.get("/tickets/{code}", response_model=schemas.TicketOut)
def get_ticket(code: str, db: Session = Depends(get_db)):
    t = db.query(models.Ticket).filter_by(code=code).first()
    if not t:
        raise HTTPException(404, "Ticket not found")
    return _ticket_out(t)


@app.get("/tickets/{code}/qr.png")
def ticket_qr(code: str, db: Session = Depends(get_db)):
    t = db.query(models.Ticket).filter_by(code=code).first()
    if not t:
        raise HTTPException(404, "Ticket not found")
    buf = io.BytesIO()
    qrcode.make(t.code).save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.post("/tickets/{code}/checkin", response_model=schemas.TicketOut,
          dependencies=[Depends(auth.require_admin)])
def check_in(code: str, db: Session = Depends(get_db)):
    t = db.query(models.Ticket).filter_by(code=code).first()
    if not t:
        raise HTTPException(404, "Ticket not found")
    if t.checked_in:
        who = t.student_name + (f", team {t.team_name}" if t.team_name else "")
        raise HTTPException(409, f"Ticket already used ({who})")
    t.checked_in = 1
    t.checked_in_at = datetime.utcnow()
    db.commit()
    return _ticket_out(t)


@app.get("/admin/stats", dependencies=[Depends(auth.require_admin)])
def stats(db: Session = Depends(get_db)):
    rows = []
    for ev in db.query(models.Event).all():
        o = _event_out(ev, db)
        sold = ev.capacity - o.seats_left  # teams for team events, people for individual events
        rows.append({"id": ev.id, "event": ev.name, "registered": sold, "seats_left": o.seats_left,
                     "revenue": sold * ev.price,
                     "team_event": o.max_team_size > 1,
                     "min_team_size": o.min_team_size, "max_team_size": o.max_team_size,
                     "people": sum(1 + len(_members(t)) for t in ev.tickets),
                     "checked_in": sum(1 for t in ev.tickets if t.checked_in)})
    return {"events": rows,
            "total_registrations": sum(r["registered"] for r in rows),
            "total_teams": sum(r["registered"] for r in rows if r["team_event"]),
            "total_individuals": sum(r["registered"] for r in rows if not r["team_event"]),
            "total_people": sum(r["people"] for r in rows),
            "total_checked_in": sum(r["checked_in"] for r in rows),
            "total_revenue": sum(r["revenue"] for r in rows)}


@app.get("/admin/events/{event_id}/registrations", dependencies=[Depends(auth.require_admin)])
def registrations(event_id: int, db: Session = Depends(get_db)):
    ev = db.get(models.Event, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    return [{"name": t.student_name, "email": t.student_email, "code": t.code,
             "team_name": t.team_name or "", "members": _members(t), "team_size": 1 + len(_members(t)),
             "checked_in": bool(t.checked_in), "checked_in_at": _iso(t.checked_in_at),
             "reminders_sent": len(t.reminders)}
            for t in ev.tickets]


@app.get("/admin/checkins", dependencies=[Depends(auth.require_admin)])
def checkins(limit: int = 100, db: Session = Depends(get_db)):
    """Everyone checked in so far, newest first."""
    rows = db.query(models.Ticket).filter(models.Ticket.checked_in == 1).all()
    rows.sort(key=lambda t: t.checked_in_at or datetime.min, reverse=True)
    return {"count": len(rows),
            "items": [{"code": t.code, "name": t.student_name, "email": t.student_email,
                       "team_name": t.team_name or "", "team_size": 1 + len(_members(t)),
                       "event": t.event.name, "event_id": t.event_id,
                       "checked_in_at": _iso(t.checked_in_at)} for t in rows[:limit]]}


@app.post("/admin/events/{event_id}/remind", dependencies=[Depends(auth.require_admin)])
def remind(event_id: int, db: Session = Depends(get_db)):
    ev = db.get(models.Event, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    return reminders.send_reminders(db, ev)
