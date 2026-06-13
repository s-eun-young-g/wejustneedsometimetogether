"""Backend for time-together — auth, groups, session ingest, Wrapped API.

Optional extra: `pip install 'time-together[server]'`. The engine (`tt`) stays
dependency-free; only this subpackage needs FastAPI/SQLModel.
"""

from __future__ import annotations

from .app import create_app, run

__all__ = ["create_app", "run"]
