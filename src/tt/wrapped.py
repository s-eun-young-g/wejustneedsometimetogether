"""Wrapped - the fun layer. Once sessions exist, every stat is a query.

All of this is computed from one person's point of view (`me`) over an optional
period. Nothing here needs the network or a phone - it's pure aggregation over
the session log, which is exactly why it's easy and testable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from .model import Session
from .sessions import GroupHang, group_moments


@dataclass
class WrappedReport:
    me: str
    total_time: timedelta
    by_person: list[tuple[str, timedelta]]          # most time first
    longest_hang: Session | None
    after_midnight: list[tuple[str, timedelta]]     # 00:00-04:00 companions
    top_places: list[tuple[str, timedelta]]
    third_place: str | None
    new_people: list[str]
    longest_streak: tuple[str, int] | None          # (person, days)
    biggest_group: GroupHang | None

    @property
    def top_person(self) -> str | None:
        return self.by_person[0][0] if self.by_person else None

    def summary(self) -> str:
        def hm(td: timedelta) -> str:
            m = int(td.total_seconds() // 60)
            return f"{m // 60}h {m % 60}m"

        lines = [f"{self.me}'s Wrapped",
                 f"Total time with people: {hm(self.total_time)}", ""]
        lines.append("Most time with:")
        for person, td in self.by_person[:5]:
            lines.append(f"  {hm(td):>8}  {person}")
        if self.longest_hang:
            h = self.longest_hang
            where = f" at {h.place}" if h.place else ""
            lines += ["", f"Longest single hang: {hm(h.duration)} with "
                          f"{h.other(self.me)}{where}"]
        if self.after_midnight:
            who, td = self.after_midnight[0]
            lines.append(f"Your after-midnight person: {who} ({hm(td)} past midnight)")
        if self.top_places:
            lines += ["", "Top places:"]
            for place, td in self.top_places[:3]:
                lines.append(f"  {hm(td):>8}  {place}")
        if self.third_place:
            lines.append(f"Your third place: {self.third_place}")
        if self.longest_streak:
            who, days = self.longest_streak
            lines.append(f"Longest streak: {days} days in a row with {who}")
        if self.biggest_group:
            g = self.biggest_group
            lines.append(f"Biggest group hang: {len(g.members)} people "
                         f"({', '.join(g.members)})")
        if self.new_people:
            lines.append(f"New people met: {', '.join(self.new_people)}")
        return "\n".join(lines)


def wrapped(sessions: list[Session], me: str,
            period: tuple[datetime, datetime] | None = None,
            home_work: tuple[str, ...] = ()) -> WrappedReport:
    in_period = [s for s in sessions
                 if period is None or (period[0] <= s.start < period[1])]
    mine = [s for s in in_period if me in s.members and len(s.members) == 2]

    by_person: dict[str, timedelta] = defaultdict(timedelta)
    places: dict[str, timedelta] = defaultdict(timedelta)
    place_visits: dict[str, int] = defaultdict(int)
    midnight: dict[str, timedelta] = defaultdict(timedelta)
    days_with: dict[str, set] = defaultdict(set)
    for s in mine:
        who = s.other(me)
        by_person[who] += s.duration
        if s.place:
            places[s.place] += s.duration
            place_visits[s.place] += 1
        mins = _window_minutes(s.start, s.end, 0, 4)
        if mins:
            midnight[who] += timedelta(minutes=mins)
        for d in _days_spanned(s.start, s.end):
            days_with[who].add(d)

    ranked = sorted(by_person.items(), key=lambda kv: kv[1], reverse=True)
    place_rank = sorted(places.items(), key=lambda kv: kv[1], reverse=True)
    # "Third place" = your *regular* spot: most-visited place that isn't home/work
    # (ranked by number of visits, then total time), not just where you logged the
    # most hours - a single long night out shouldn't outrank the daily coffee.
    candidates = [(p, place_visits[p], places[p]) for p in places if p not in home_work]
    candidates.sort(key=lambda c: (c[1], c[2]), reverse=True)
    third = candidates[0][0] if candidates else None

    streak = None
    for who, days in days_with.items():
        n = _longest_run(days)
        if streak is None or n > streak[1]:
            streak = (who, n)

    new_people = _new_people(sessions, me, period) if period else []

    groups = [g for g in group_moments(sessions) if me in g.members]
    biggest = max(groups, key=lambda g: (len(g.members), g.minutes), default=None)

    return WrappedReport(
        me=me,
        total_time=sum(by_person.values(), timedelta()),
        by_person=ranked,
        longest_hang=max(mine, key=lambda s: s.duration, default=None),
        after_midnight=sorted(midnight.items(), key=lambda kv: kv[1], reverse=True),
        top_places=place_rank,
        third_place=third,
        new_people=new_people,
        longest_streak=streak,
        biggest_group=biggest,
    )


# -- helpers ---------------------------------------------------------------

def _window_minutes(start: datetime, end: datetime, lo_hour: int, hi_hour: int) -> float:
    """Minutes of [start, end] that fall inside [lo_hour, hi_hour) on any day."""
    total = 0.0
    day = start.date()
    while datetime.combine(day, time()) <= end:
        wlo = datetime.combine(day, time(lo_hour, 0))
        whi = datetime.combine(day, time(hi_hour, 0))
        overlap = (min(end, whi) - max(start, wlo)).total_seconds()
        if overlap > 0:
            total += overlap / 60.0
        day = day + timedelta(days=1)
    return total


def _days_spanned(start: datetime, end: datetime) -> list:
    days, day = [], start.date()
    while day <= end.date():
        days.append(day)
        day = day + timedelta(days=1)
    return days


def _longest_run(days: set) -> int:
    if not days:
        return 0
    ordered = sorted(days)
    best = run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        best = max(best, run)
    return best


def _new_people(sessions: list[Session], me: str, period) -> list[str]:
    first_seen: dict[str, datetime] = {}
    for s in sorted(sessions, key=lambda s: s.start):
        if me in s.members and len(s.members) == 2:
            who = s.other(me)
            first_seen.setdefault(who, s.start)
    return [who for who, first in first_seen.items() if period[0] <= first < period[1]]
