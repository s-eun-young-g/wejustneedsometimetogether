from datetime import datetime, timedelta

from tt.model import Sighting, StitchParams
from tt.sessions import group_moments, stitch_sessions

BASE = datetime(2026, 6, 1, 9, 0)


def pings(a, b, start_min, end_min, step=1, rssi=-62, place="cafe"):
    out = []
    t = start_min
    while t <= end_min:
        out.append(Sighting(a, b, BASE + timedelta(minutes=t), rssi, place))
        t += step
    return out


def test_one_clean_session():
    s = stitch_sessions(pings("you", "alex", 0, 40))
    assert len(s) == 1
    assert s[0].members == ("alex", "you")
    assert s[0].minutes == 40
    assert s[0].place == "cafe"


def test_short_gap_is_bridged():
    # two runs 0-10 and 13-25, gap of 3 min (< default 5) -> one session
    sightings = pings("you", "alex", 0, 10) + pings("you", "alex", 13, 25)
    s = stitch_sessions(sightings)
    assert len(s) == 1
    assert s[0].minutes == 25


def test_long_gap_splits():
    # gap of 20 min -> two sessions
    sightings = pings("you", "alex", 0, 10) + pings("you", "alex", 30, 45)
    s = stitch_sessions(sightings)
    assert len(s) == 2


def test_fleeting_pass_dropped():
    # 2-minute brush-by is below t_min (5) -> dropped
    assert stitch_sessions(pings("you", "stranger", 0, 2)) == []


def test_weak_signal_ignored():
    params = StitchParams(rssi_threshold=-70)
    assert stitch_sessions(pings("you", "alex", 0, 40, rssi=-85), params) == []


def test_separate_pairs_dont_merge():
    sightings = pings("you", "alex", 0, 30) + pings("you", "sam", 0, 30)
    s = stitch_sessions(sightings)
    assert {tuple(x.members) for x in s} == {("alex", "you"), ("sam", "you")}


def test_group_moment_detects_three_together():
    # you-alex, you-sam, alex-sam all overlap 0-30 -> a 3-person group hang
    sightings = (pings("you", "alex", 0, 30) + pings("you", "sam", 0, 30)
                 + pings("alex", "sam", 0, 30))
    sessions = stitch_sessions(sightings)
    groups = group_moments(sessions)
    assert len(groups) == 1
    assert groups[0].members == ("alex", "sam", "you")


def test_no_group_when_only_pairs():
    sightings = pings("you", "alex", 0, 30) + pings("you", "sam", 0, 30)
    # you with each, but alex & sam never see each other -> still a 3-chain!
    # without alex-sam edge they're a connected component of 3 via you.
    sessions = stitch_sessions(sightings)
    groups = group_moments(sessions)
    assert len(groups) == 1 and len(groups[0].members) == 3
