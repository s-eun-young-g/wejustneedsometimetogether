from datetime import datetime, timedelta

from tt.sessions import stitch_sessions
from tt.simulate import demo_scenario, generate_sightings
from tt.wrapped import wrapped

BASE = datetime(2026, 6, 1, 0, 0)


def _report(drop=0.0):
    sightings = generate_sightings(demo_scenario(BASE), drop=drop)
    sessions = stitch_sessions(sightings)
    return wrapped(sessions, me="you",
                   period=(BASE, BASE + timedelta(days=7)),
                   home_work=("Office",))


def test_top_person_is_alex():
    r = _report()
    # alex appears across many days; should be #1 by time
    assert r.top_person == "alex"


def test_after_midnight_companion():
    r = _report()
    # the Friday night out runs to 01:30, with alex and sam
    who = {p for p, _ in r.after_midnight}
    assert {"alex", "sam"} <= who


def test_third_place_excludes_office():
    r = _report()
    assert r.third_place != "Office"
    # Java House (daily coffee) is the most-frequented non-work place
    assert r.third_place == "Java House"


def test_new_person_jordan():
    r = _report()
    assert "jordan" in r.new_people


def test_streak_with_alex():
    r = _report()
    who, days = r.longest_streak
    assert who == "alex"
    assert days >= 4                      # Mon–Thu coffee streak


def test_biggest_group_is_friday_trio():
    r = _report()
    assert r.biggest_group is not None
    assert set(r.biggest_group.members) == {"alex", "sam", "you"}


def test_survives_dropped_pings():
    # heavy Bluetooth flakiness shouldn't destroy the headline results
    r = _report(drop=0.4)
    assert r.top_person == "alex"
    assert r.total_time.total_seconds() > 0
