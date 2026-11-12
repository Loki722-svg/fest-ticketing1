from typing import Optional
from pydantic import BaseModel


class EventCreate(BaseModel):
    name: str
    description: str = ""
    venue: str = ""
    date: str = ""
    price: float = 0.0
    capacity: int = 100
    min_team_size: int = 1
    max_team_size: int = 1


class EventOut(EventCreate):
    id: int
    seats_left: int


class Member(BaseModel):
    name: str
    email: str = ""


class RegisterIn(BaseModel):
    event_id: int
    student_name: str          # the person registering (team leader for team events)
    student_email: str
    team_name: str = ""
    members: list[Member] = []  # the other team members (not the leader)


class TicketOut(BaseModel):
    code: str
    event_id: int
    event_name: str
    student_name: str
    student_email: str
    checked_in: bool
    team_name: str = ""
    members: list[Member] = []
    team_size: int = 1
    checked_in_at: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str
