"""The backend: auth, groups, session ingest, and a Wrapped endpoint that reuses
the `tt` engine.

`create_app(db_url)` is a factory so tests can spin up a fresh in-memory database.
Auth is intentionally minimal for the MVP: register returns a bearer token that
identifies the user on later requests (a real build would use Sign in with Apple /
phone OTP — swapping that in only touches `register` and `current_user`).
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, create_engine, select

from tt.model import Session as EngineSession
from tt.wrapped import wrapped as compute_wrapped

from .models import (Group, GroupIn, JoinIn, Membership, RegisterIn, Sess,
                     SessionsIn, User, utcnow)


def create_app(db_url: str = "sqlite:///tt.db") -> FastAPI:
    in_memory = db_url in ("sqlite://", "sqlite:///:memory:")
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if in_memory else None,
    )
    SQLModel.metadata.create_all(engine)

    app = FastAPI(title="we just need some time together")

    def db():
        with DBSession(engine) as session:
            yield session

    def current_user(authorization: str | None = Header(None),
                     session: DBSession = Depends(db)) -> User:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        user = session.exec(select(User).where(User.token == token)).first()
        if not user:
            raise HTTPException(401, "invalid token")
        return user

    def my_group_ids(session: DBSession, user_id: int) -> set[int]:
        rows = session.exec(select(Membership.group_id)
                            .where(Membership.user_id == user_id)).all()
        return set(rows)

    # -- auth ---------------------------------------------------------------

    @app.post("/auth/register")
    def register(body: RegisterIn, session: DBSession = Depends(db)):
        user = User(name=body.name, token=secrets.token_urlsafe(24))
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"user_id": user.id, "name": user.name, "token": user.token}

    @app.get("/me")
    def me(user: User = Depends(current_user)):
        return {"user_id": user.id, "name": user.name}

    # -- groups -------------------------------------------------------------

    @app.post("/groups")
    def create_group(body: GroupIn, user: User = Depends(current_user),
                     session: DBSession = Depends(db)):
        group = Group(name=body.name, invite_code=secrets.token_hex(4))
        session.add(group)
        session.commit()
        session.refresh(group)
        session.add(Membership(user_id=user.id, group_id=group.id))
        session.commit()
        return {"group_id": group.id, "name": group.name, "invite_code": group.invite_code}

    @app.post("/groups/join")
    def join_group(body: JoinIn, user: User = Depends(current_user),
                   session: DBSession = Depends(db)):
        group = session.exec(select(Group)
                             .where(Group.invite_code == body.invite_code)).first()
        if not group:
            raise HTTPException(404, "no group with that invite code")
        exists = session.exec(select(Membership).where(
            Membership.user_id == user.id, Membership.group_id == group.id)).first()
        if not exists:
            session.add(Membership(user_id=user.id, group_id=group.id))
            session.commit()
        return {"group_id": group.id, "name": group.name}

    @app.get("/groups")
    def list_groups(user: User = Depends(current_user), session: DBSession = Depends(db)):
        out = []
        for gid in my_group_ids(session, user.id):
            group = session.get(Group, gid)
            member_ids = session.exec(select(Membership.user_id)
                                      .where(Membership.group_id == gid)).all()
            members = [{"id": u.id, "name": u.name}
                       for u in (session.get(User, mid) for mid in member_ids) if u]
            out.append({"id": gid, "name": group.name, "members": members})
        return out

    # -- sessions -----------------------------------------------------------

    @app.post("/sessions")
    def ingest(body: SessionsIn, user: User = Depends(current_user),
               session: DBSession = Depends(db)):
        mine = my_group_ids(session, user.id)
        ingested = 0
        for item in body.sessions:
            peer_groups = my_group_ids(session, item.peer_id)
            if not (mine & peer_groups):
                continue                      # no shared group → not allowed to log
            a, b = sorted((user.id, item.peer_id))
            session.add(Sess(user_a=a, user_b=b, start=item.start,
                             end=item.end, place=item.place))
            ingested += 1
        session.commit()
        return {"ingested": ingested}

    # -- wrapped ------------------------------------------------------------

    @app.get("/wrapped")
    def get_wrapped(user: User = Depends(current_user), group_id: int | None = None,
                    days: int | None = None, home_work: str = "",
                    session: DBSession = Depends(db)):
        # Which people's sessions are in scope.
        if group_id is not None:
            if group_id not in my_group_ids(session, user.id):
                raise HTTPException(403, "not a member of that group")
            member_ids = set(session.exec(select(Membership.user_id)
                                          .where(Membership.group_id == group_id)).all())
        else:
            member_ids = {user.id}
            for gid in my_group_ids(session, user.id):
                member_ids |= set(session.exec(select(Membership.user_id)
                                               .where(Membership.group_id == gid)).all())

        rows = session.exec(select(Sess).where(
            Sess.user_a.in_(member_ids), Sess.user_b.in_(member_ids))).all()
        rows = _merge_overlapping(rows)

        names = {uid: (session.get(User, uid).name if session.get(User, uid) else str(uid))
                 for uid in member_ids}
        engine_sessions = [
            EngineSession(members=tuple(sorted((names[r.user_a], names[r.user_b]))),
                          start=r.start, end=r.end, place=r.place)
            for r in rows
        ]

        period = None
        if days:
            now = utcnow()
            period = (now - timedelta(days=days), now)
        hw = tuple(h.strip() for h in home_work.split(",") if h.strip())
        report = compute_wrapped(engine_sessions, me=user.name, period=period, home_work=hw)
        return _wrapped_json(report)

    return app


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _merge_overlapping(rows: list[Sess]) -> list[Sess]:
    """Reconcile duplicate uploads: both phones in a hang upload the same session,
    so merge overlapping (or touching) sessions for the same pair into one."""
    by_pair: dict[tuple[int, int], list[Sess]] = {}
    for r in rows:
        by_pair.setdefault((r.user_a, r.user_b), []).append(r)
    merged: list[Sess] = []
    for (a, b), group in by_pair.items():
        group.sort(key=lambda r: r.start)
        cur = None
        for r in group:
            if cur and r.start <= cur.end:
                if r.end > cur.end:
                    cur.end = r.end
                cur.place = cur.place or r.place
            else:
                cur = Sess(user_a=a, user_b=b, start=r.start, end=r.end, place=r.place)
                merged.append(cur)
    return merged


def _td_minutes(td) -> int:
    return int(td.total_seconds() // 60)


def _wrapped_json(r) -> dict:
    return {
        "me": r.me,
        "total_minutes": _td_minutes(r.total_time),
        "top_person": r.top_person,
        "by_person": [{"name": n, "minutes": _td_minutes(t)} for n, t in r.by_person],
        "longest_hang": (None if not r.longest_hang else {
            "with": r.longest_hang.other(r.me),
            "minutes": _td_minutes(r.longest_hang.duration),
            "place": r.longest_hang.place,
        }),
        "after_midnight": [{"name": n, "minutes": _td_minutes(t)} for n, t in r.after_midnight],
        "top_places": [{"place": p, "minutes": _td_minutes(t)} for p, t in r.top_places],
        "third_place": r.third_place,
        "new_people": r.new_people,
        "longest_streak": (None if not r.longest_streak
                           else {"with": r.longest_streak[0], "days": r.longest_streak[1]}),
        "biggest_group": (None if not r.biggest_group
                          else {"members": list(r.biggest_group.members),
                                "minutes": int(r.biggest_group.minutes)}),
    }


def run() -> None:  # console-script entry: `tt-server`
    import uvicorn
    uvicorn.run(create_app(os.environ.get("TT_DB_URL", "sqlite:///tt.db")),
                host="127.0.0.1", port=8000)
