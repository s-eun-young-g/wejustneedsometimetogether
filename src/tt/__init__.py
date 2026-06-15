"""time-together (TT) - a co-presence engine.

Records how much time you spend physically with people in your group (not where
you are when you're alone), and turns it into a "Wrapped." This package is the
testable core - sightings -> sessions -> analytics - that the iOS app and backend
will sit on top of.
"""

from __future__ import annotations

from .model import Session, Sighting, StitchParams
from .sessions import GroupHang, group_moments, stitch_sessions
from .wrapped import WrappedReport, wrapped

__all__ = [
    "Sighting", "Session", "StitchParams",
    "stitch_sessions", "group_moments", "GroupHang",
    "wrapped", "WrappedReport",
]

__version__ = "0.1.0"
