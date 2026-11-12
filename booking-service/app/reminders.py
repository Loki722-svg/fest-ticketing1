"""Reminder logic: manual (admin button) and automatic (background loop)."""
import asyncio
import json
import os
from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models, mailer
from .database import SessionLocal


def _recipients(t: models.Ticket) -> list:
    """Leader first, then team members who gave an email address."""
    out = [(t.student_name, t.student_email)]
    try:
        members = json.loads(t.members) if t.members else []
    except ValueError:
        members = []
    out += [(m.get("name", ""), m["email"]) for m in members if m.get("email")]
    return out


def send_reminders(db: Session, event: models.Event, only_new: bool = False) -> dict:
    """Email everyone registered for `event` (whole team) who has not checked in yet."""
    sent = failed = skipped = 0
    for t in event.tickets:
        if t.checked_in:
            continue
        if only_new and any(r.status != "failed" for r in t.reminders):
            skipped += 1
            continue
        team_line = f"Team: {t.team_name}\n" if t.team_name else ""
        leader_status = None
        for name, email in _recipients(t):
            body = (
                f"Hi {name},\n\nReminder: {event.name} is on {event.date} "
                f"at {event.venue}.\n{team_line}Your ticket code is {t.code}. "
                f"Show the QR code at the entrance.\n\nSee you there!"
            )
            status = mailer.send_email(email, f"Reminder: {event.name}", body)
            leader_status = leader_status or status
            if status == "failed":
                failed += 1
            else:
                sent += 1
        db.add(models.Reminder(ticket_id=t.id, status=leader_status))
    db.commit()
    return {"event": event.name, "sent": sent, "failed": failed, "skipped": skipped}


def run_auto_reminders() -> list:
    """Remind participants of events happening today or tomorrow (once each)."""
    db = SessionLocal()
    try:
        days = {date.today().isoformat(), (date.today() + timedelta(days=1)).isoformat()}
        events = db.query(models.Event).filter(models.Event.date.in_(days)).all()
        return [send_reminders(db, e, only_new=True) for e in events]
    finally:
        db.close()


async def reminder_loop():
    interval = int(os.getenv("REMINDER_INTERVAL_SECONDS", "3600"))
    while True:
        try:
            await asyncio.to_thread(run_auto_reminders)
        except Exception as exc:  # keep the loop alive
            print("auto reminder error:", exc)
        await asyncio.sleep(interval)
