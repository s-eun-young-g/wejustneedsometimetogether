"""Database tables and request/response shapes for the backend.

Privacy-shaped on purpose: the only thing stored about your whereabouts is a
**session** — two people who were together, when, and (optionally) where. There is
no continuous-location table because the phone never uploads one. A session is
between two *users*, not scoped to a group; a group just decides who can see it
(both participants must share a group for it to count).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Naive UTC 'now' — naive throughout so it never clashes with the naive
    timestamps phones upload."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    token: str = Field(index=True, unique=True)
    created: datetime = Field(default_factory=utcnow)


class Group(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    invite_code: str = Field(index=True, unique=True)
    created: datetime = Field(default_factory=utcnow)


class Membership(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    group_id: int = Field(index=True)


class Sess(SQLModel, table=True):
    """A pairwise co-presence record. user_a < user_b is enforced on write so the
    pair has one canonical form regardless of who uploaded it."""
    id: int | None = Field(default=None, primary_key=True)
    user_a: int = Field(index=True)
    user_b: int = Field(index=True)
    start: datetime
    end: datetime
    place: str | None = None
    created: datetime = Field(default_factory=utcnow)


# -- request bodies ---------------------------------------------------------

class RegisterIn(SQLModel):
    name: str


class GroupIn(SQLModel):
    name: str


class JoinIn(SQLModel):
    invite_code: str


class SessionIn(SQLModel):
    peer_id: int
    start: datetime
    end: datetime
    place: str | None = None


class SessionsIn(SQLModel):
    sessions: list[SessionIn]
