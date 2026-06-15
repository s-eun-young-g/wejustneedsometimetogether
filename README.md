# we just need some time together (title wip)

How much time do you actually spend with your people, and where, and when? Time Together (TT)
notices when you and someone in your group are physically together, logs the time
and place, and at the end gives you a "Wrapped" for your friendships. Think Life360,
but wholesome and far less surveillance-heavy.

It is a co-presence recorder, not a location tracker, and that distinction is the
point. TT never needs to know where you are when you are alone; it only cares about
time you spend with someone who is also in your group and opted in. Your solo
whereabouts never leave your phone.

```bash
pip install -e .
tt demo
```

Example output:

```
you's Wrapped
Total time with people: 19h 20m

Most time with:
    12h 5m  alex
    5h 15m  sam
     2h 0m  jordan

Longest single hang: 5h 0m with alex at alex's place
Your after-midnight person: alex (1h 30m past midnight)
Top places:  The Crown, alex's place, Java House
Your third place: Java House
Longest streak: 7 days in a row with alex
Biggest group hang: 3 people (alex, sam, you)
```

That report is computed from a simulated week, no phone involved, which is the point
of building the engine first.

## How it works

```
sighting {a, b, ts, rssi, place}  (Bluetooth)
   -> stitch -> session {members, start, end, place}
   -> aggregate -> Wrapped {top person, after-midnight, places, streaks, group hangs}
```

- `sessions.py`: `stitch_sessions` turns a noisy Bluetooth sighting stream into clean
  sessions (bridges dropouts under `t_gap`, discards fleeting passes under `t_min`).
  `group_moments` finds when 3 or more people were together at once (connected
  components over a sweep of the pairwise sessions).
- `wrapped.py`: pure aggregation over the session log: time per person,
  after-midnight companion, top places, your third place (most-visited spot that
  isn't home or work), streaks, biggest group hang, new people.
- `simulate.py`: scripts a week of hangs into sightings so the whole pipeline is
  testable without hardware.

This package is the testable core; the backend and iOS app sit on top of it.

## Backend

A small FastAPI plus SQLModel service (SQLite for dev) that the phone talks to. It
stores only pairwise session summaries, never continuous location, and reuses the
`tt` engine to compute Wrapped server-side.

```bash
pip install -e '.[server]'
tt-server                       # http://127.0.0.1:8000  (docs at /docs)
```

| Endpoint | Does |
|---|---|
| `POST /auth/register` | create a user, get a bearer token (MVP auth; Sign in with Apple later) |
| `POST /groups`, `POST /groups/join`, `GET /groups` | create / join (by invite code) / list your groups |
| `POST /sessions` | upload pairwise session summaries (only logs with people who share a group) |
| `GET /wrapped` | your Wrapped (optionally `?group_id=` / `?days=` / `?home_work=`) |

Two design points: a session is between two people (a group only governs who may
log or see it), and duplicate uploads from both phones in a hang are reconciled
(merged) so a hang counts once.

## The eventual app (design summary)

- Detection (hybrid): Bluetooth LE decides who you are with (real proximity, works
  indoors, low battery use); GPS fires only during an active hang to tag where.
  Mutual, group-scoped consent is enforced by the mechanism: no app on their phone,
  no Bluetooth token, no log.
- Privacy: sessions are stitched on-device; only summaries (who, when, how long,
  place) leave the phone, never your continuous location.
- Platform: iOS first (Core Bluetooth dual central plus peripheral with state
  restoration; Core Location only while a session is active).
- Biggest risk: reliable background iOS-to-iOS Bluetooth detection, to be de-risked
  on two real phones before building the app.

## Current status

Works and tested: 21 passing tests. The backend half is real: the co-presence engine
(noisy Bluetooth sightings to clean sessions to Wrapped) and a FastAPI service (auth,
groups, ingest, Wrapped) smoke-tested over actual HTTP. You can watch a full Wrapped
fall out of a simulated week now with `tt demo`.

Still drafting: the iOS app isn't built yet, on purpose. There is one make-or-break
question: can two iPhones in your pocket reliably notice each other over Bluetooth in
the background? iOS is stingy about that. So the next step is not "build the app," it
is a small two-phone test to get a real go/no-go first.

Ideas: the de-risk test, then the iOS client (detect, upload, a Wrapped screen), then
group analytics (your 2am person, your third place, biggest group hang).

### How it got here

- Engine and simulator (done): sightings to sessions to Wrapped, fully tested.
- Backend (done): FastAPI auth, groups/invites, session ingest (shared-group plus
  duplicate reconcile), Wrapped API, reuses the engine, tested via TestClient.
- iOS de-risk test (next): two phones, background co-presence, go/no-go.
- iOS app: detect-and-upload client plus Wrapped screen.

## Tests

```bash
python -m pytest -q
```
