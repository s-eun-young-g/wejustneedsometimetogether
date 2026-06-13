"""Command-line entry point.

  tt demo            run the built-in week-in-the-life scenario and print a Wrapped
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from .sessions import stitch_sessions
from .simulate import demo_scenario, generate_sightings
from .wrapped import wrapped


def _cmd_demo(args) -> int:
    base = datetime(2026, 6, 1, 0, 0)        # a fixed Monday, for reproducibility
    hangs = demo_scenario(base)
    sightings = generate_sightings(hangs, drop=args.drop)
    sessions = stitch_sessions(sightings)
    report = wrapped(sessions, me="you",
                     period=(base, base + timedelta(days=7)),
                     home_work=("Office",))
    print(f"(simulated {len(sightings)} sightings → {len(sessions)} sessions)\n")
    print(report.summary())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tt", description="time-together — a co-presence + Wrapped engine.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="run the built-in scenario and print a Wrapped")
    p_demo.add_argument("--drop", type=float, default=0.0,
                        help="fraction of Bluetooth pings to drop (simulate flakiness)")
    p_demo.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
