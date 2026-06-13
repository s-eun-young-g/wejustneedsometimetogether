"""Core types for the co-presence engine.

The app is a *co-presence recorder*, not a location tracker: the only things that
ever become durable records are **sessions** — spans of time two (or more) people
in a group were physically together. A session is built from raw **sightings**
(one phone seeing another over Bluetooth), and the only location ever attached is
the place of a session that's already happening — never your solo whereabouts.

Everything here is plain data so the engine can be unit-tested against simulated
days with no phone in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Sighting:
    """One device seeing another at a moment in time.

    `a`/`b` are user ids (order doesn't matter — `pair` normalizes them). `rssi`
    is Bluetooth signal strength (higher = closer; ~-60 near, ~-90 far). `place`
    is the on-device-resolved place label, present only while a hang is active."""
    a: str
    b: str
    ts: datetime
    rssi: int = -60
    place: str | None = None

    @property
    def pair(self) -> tuple[str, str]:
        return tuple(sorted((self.a, self.b)))


@dataclass
class Session:
    """A durable co-presence record: these people were together start..end."""
    members: tuple[str, ...]          # sorted; pairwise sessions have two
    start: datetime
    end: datetime
    place: str | None = None

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    @property
    def minutes(self) -> float:
        return self.duration.total_seconds() / 60.0

    def other(self, me: str) -> str:
        """For a pairwise session, the member who isn't `me`."""
        rest = [m for m in self.members if m != me]
        return rest[0] if rest else me


@dataclass(frozen=True)
class StitchParams:
    """Knobs that turn a noisy sighting stream into clean sessions — these *are*
    the product's feel.

    rssi_threshold : ignore sightings weaker than this (too far to count as "together")
    t_gap          : bridge dropouts shorter than this within one session
    t_min          : discard sessions shorter than this as noise / fleeting passes
    """
    rssi_threshold: int = -80
    t_gap: timedelta = timedelta(minutes=5)
    t_min: timedelta = timedelta(minutes=5)
