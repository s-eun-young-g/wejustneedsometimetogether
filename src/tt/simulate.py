"""Simulator — generate sightings from a script of hangs, so we can exercise the
whole pipeline (sightings → sessions → Wrapped) with no phones.

A `Hang` says "these people were together at this place from start to end." We
emit a Bluetooth sighting for every pair, every `sample` interval, with optional
RSSI jitter and dropped pings so the stitcher has realistic noise to clean up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations

from .model import Sighting


@dataclass
class Hang:
    people: tuple[str, ...]
    start: datetime
    end: datetime
    place: str


def generate_sightings(hangs: list[Hang], sample: timedelta = timedelta(minutes=1),
                       rssi: int = -62, drop: float = 0.0) -> list[Sighting]:
    """Emit pairwise sightings across each hang. `drop` (0..1) skips that fraction
    of pings deterministically to mimic Bluetooth flakiness."""
    out: list[Sighting] = []
    tick = 0
    for hang in hangs:
        for a, b in combinations(sorted(hang.people), 2):
            t = hang.start
            while t <= hang.end:
                tick += 1
                if not (drop and (tick % max(1, round(1 / drop)) == 0)):
                    out.append(Sighting(a, b, t, rssi, hang.place))
                t += sample
    return out


def demo_scenario(base: datetime) -> list[Hang]:
    """A week in the life of `you`, designed to produce a colourful Wrapped:
    a daily coffee with Alex, a long Friday night out (a 3-person group hang that
    runs past midnight), and a one-off new friend."""
    def at(day: int, hour: int, minute: int = 0) -> datetime:
        return base + timedelta(days=day, hours=hour, minutes=minute)

    hangs = [
        # Mon–Thu morning coffee with Alex (a steady streak, at the same café)
        Hang(("you", "alex"), at(0, 9), at(0, 9, 40), "Java House"),
        Hang(("you", "alex"), at(1, 9), at(1, 9, 35), "Java House"),
        Hang(("you", "alex"), at(2, 9), at(2, 9, 50), "Java House"),
        Hang(("you", "alex"), at(3, 9), at(3, 9, 30), "Java House"),
        # Wed lunch with Sam at the office
        Hang(("you", "sam"), at(2, 12, 30), at(2, 13, 15), "Office"),
        # Fri night out: you + alex + sam, running past midnight
        Hang(("you", "alex", "sam"), at(4, 21), at(5, 1, 30), "The Crown"),
        # Sat: meet a new person, jordan, at a park
        Hang(("you", "jordan"), at(5, 15), at(5, 17), "Riverside Park"),
        # Sun: long lazy afternoon with alex
        Hang(("you", "alex"), at(6, 13), at(6, 18), "alex's place"),
    ]
    return hangs
