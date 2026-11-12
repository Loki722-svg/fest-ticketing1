import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    venue = Column(String, default="")
    date = Column(String, default="")
    price = Column(Float, default=0.0)
    capacity = Column(Integer, default=100)  # number of teams (or people for individual events)
    min_team_size = Column(Integer, default=1)
    max_team_size = Column(Integer, default=1)  # 1 = individual event
    tickets = relationship("Ticket", back_populates="event", cascade="all, delete-orphan")


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex[:12].upper())
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    student_name = Column(String, nullable=False)
    student_email = Column(String, nullable=False)
    payment_ref = Column(String)
    checked_in = Column(Integer, default=0)
    checked_in_at = Column(DateTime)
    team_name = Column(String)
    members = Column(Text)  # JSON list of the other team members: [{"name":..., "email":...}]
    created_at = Column(DateTime, default=datetime.utcnow)
    event = relationship("Event", back_populates="tickets")
    reminders = relationship("Reminder", back_populates="ticket", cascade="all, delete-orphan")


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    status = Column(String, default="sent")
    sent_at = Column(DateTime, default=datetime.utcnow)
    ticket = relationship("Ticket", back_populates="reminders")
