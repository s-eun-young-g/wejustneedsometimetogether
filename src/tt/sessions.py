"""Stitch raw sightings into clean sessions, and find group hangs.

`stitch_sessions` is the core: per pair of people, sort their sightings, drop the
weak ones, then split into runs wherever there's a gap longer than `t_gap`. Each
run becomes a session if it lasted at least `t_min`. This is the noise-rejection
that makes "you and Alex, 9:00-11:30 at The Crown" fall out of a jittery stream of
Bluetooth blips.

`group_moments` then asks a different question - *when were 3+ people together at
once?* - by sweeping the pairwise sessions as edges over time and looking for
connected components of three or more.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from .model import Session, Sighting, StitchParams


def stitch_sessions(sightings: list[Sighting],
                    params: StitchParams = StitchParams()) -> list[Session]:
    """Turn sightings into sessions (one timeline per pair)."""
    by_pair: dict[tuple[str, str], list[Sighting]] = defaultdict(list)
    for s in sightings:
        if s.rssi >= params.rssi_threshold:
            by_pair[s.pair].append(s)

    sessions: list[Session] = []
    for pair, sights in by_pair.items():
        sights.sort(key=lambda s: s.ts)
        run = [sights[0]]
        for prev, cur in zip(sights, sights[1:]):
            if cur.ts - prev.ts <= params.t_gap:
                run.append(cur)
            else:
                sessions.append(_session_from_run(pair, run))
                run = [cur]
        sessions.append(_session_from_run(pair, run))

    sessions = [s for s in sessions if s.duration >= params.t_min]
    sessions.sort(key=lambda s: s.start)
    return sessions


def _session_from_run(pair: tuple[str, str], run: list[Sighting]) -> Session:
    places = [s.place for s in run if s.place]
    place = Counter(places).most_common(1)[0][0] if places else None
    return Session(members=pair, start=run[0].ts, end=run[-1].ts, place=place)


# ---------------------------------------------------------------------------
# Group hangs: when 3+ people were together at the same time.
# ---------------------------------------------------------------------------

@dataclass
class GroupHang:
    members: tuple[str, ...]
    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0


def group_moments(sessions: list[Session], min_size: int = 3) -> list[GroupHang]:
    """Find spans where a connected group of >= min_size people overlapped.

    Each pairwise session is an edge active over [start, end]. We sweep the
    distinct event times; in each interval the active edges form a graph, and any
    connected component of >= min_size people is a group hang for that interval.
    Adjacent intervals with the same member set are merged."""
    pair_sessions = [s for s in sessions if len(s.members) == 2]
    if not pair_sessions:
        return []

    times = sorted({t for s in pair_sessions for t in (s.start, s.end)})
    raw: list[tuple[frozenset[str], datetime, datetime]] = []
    for lo, hi in zip(times, times[1:]):
        mid = lo + (hi - lo) / 2
        edges = [s.members for s in pair_sessions if s.start <= mid < s.end]
        for comp in _components(edges):
            if len(comp) >= min_size:
                raw.append((comp, lo, hi))

    # Merge temporally-adjacent intervals that hold the same set of people.
    raw.sort(key=lambda r: r[1])
    merged: list[GroupHang] = []
    for comp, lo, hi in raw:
        if merged and frozenset(merged[-1].members) == comp and merged[-1].end == lo:
            merged[-1].end = hi
        else:
            merged.append(GroupHang(tuple(sorted(comp)), lo, hi))
    return merged


def _components(edges: list[tuple[str, str]]) -> list[frozenset[str]]:
    """Connected components of the graph formed by these edges (union-find)."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        parent[find(x)] = find(y)

    for a, b in edges:
        union(a, b)
    groups: dict[str, set[str]] = defaultdict(set)
    for node in parent:
        groups[find(node)].add(node)
    return [frozenset(g) for g in groups.values()]
