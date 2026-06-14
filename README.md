# we just need some time together

How much time do you *actually* spend with your people — and where, and when? TT
quietly notices when you and someone in your group are physically together, logs
the time + place, and at the end hands you a little "Wrapped" for your friendships.
Think Life360, but make it wholesome (and way less surveillance-y).

**It's a co-presence recorder, not a location tracker** — and that distinction is
the whole point. TT never needs to know where you are when you're *alone*; it only
ever cares about time you spend *with* someone who's also in your group and opted
in. Your solo whereabouts never leave your phone.

```bash
pip install -e .
tt demo
```

```
✨ you's Wrapped ✨
Total time with people: 19h 20m

Most time with:
    12h 5m  alex
    5h 15m  sam
     2h 0m  jordan

Longest single hang: 5h 0m with alex at alex's place
Your after-midnight person: alex (1h 30m past midnight)
Top places:  The Crown · alex's place · Java House
Your third place: Java House
Longest streak: 7 days in a row with alex
Biggest group hang: 3 people (alex, sam, you)
```

That report is computed from a *simulated* week — no phone involved — which is the
whole point of building the engine first.

## How it works

```
 sighting        ── stitch ──▶   session         ── aggregate ──▶  Wrapped
 {a, b, ts,                      {members, start,                  {top person,
  rssi, place}                    end, place}                      after-midnight,
 (Bluetooth)                                                       places, streaks,
                                                                   group hangs}
```

- **`sessions.py`** — `stitch_sessions` turns a noisy Bluetooth sighting stream
  into clean sessions (bridge dropouts under `t_gap`, discard fleeting passes
  under `t_min`). `group_moments` finds when 3+ people were together at once
  (connected components over a sweep of the pairwise sessions).
- **`wrapped.py`** — pure aggregation over the session log: time per person,
  after-midnight companion, top places, your *third place* (most-*visited* spot
  that isn't home/work), streaks, biggest group hang, new people.
- **`simulate.py`** — scripts a week of hangs into sightings so the whole pipeline
  is testable without hardware.

This package is the **testable core**; the backend and iOS app sit on top of it.

## Backend

A small FastAPI + SQLModel service (SQLite for dev) that the phone talks to. It
stores only pairwise session summaries — never continuous location — and reuses
the `tt` engine to compute Wrapped server-side.

```bash
pip install -e '.[server]'
tt-server                       # http://127.0.0.1:8000  (docs at /docs)
```

| Endpoint | Does |
|---|---|
| `POST /auth/register` | create a user, get a bearer token (MVP auth; Sign in with Apple later) |
| `POST /groups` · `POST /groups/join` · `GET /groups` | create / join (by invite code) / list your groups |
| `POST /sessions` | upload pairwise session summaries — only logs with people who share a group |
| `GET /wrapped` | your Wrapped (optionally `?group_id=` / `?days=` / `?home_work=`) |

Two design points baked in: a session is between two *people* (a group only governs
who may log/see it), and duplicate uploads from both phones in a hang are
**reconciled** (merged) so a hang counts once.

## The eventual app (design summary)

- **Detection — hybrid:** Bluetooth LE decides *who* you're with (measures real
  proximity, works indoors, sips battery); GPS fires only *during* an active hang
  to tag *where*. Mutual, group-scoped consent is enforced by the mechanism — no
  app on their phone, no Bluetooth token, no log.
- **Privacy:** sessions are stitched on-device; only summaries (who / when / how
  long / place) leave the phone — never your continuous location.
- **Platform:** iOS first (Core Bluetooth dual central+peripheral + state
  restoration; Core Location only while a session is active).
- **Biggest risk:** reliable *background* iOS↔iOS Bluetooth detection — to be
  de-risked on two real phones before building the app.

## Current status (the honest version)

**✅ works & tested** — 21 passing tests. The whole *backend* half of the dream is
real: the co-presence engine (noisy Bluetooth sightings → clean sessions →
Wrapped) and a FastAPI service (auth, groups, ingest, Wrapped) that I've smoke-
tested over actual HTTP. You can watch a full Wrapped fall out of a simulated week
right now with `tt demo`.

**🚧 still drafting** — the actual iOS app isn't built yet, on purpose. There's one
make-or-break question hiding under all of this: *can two iPhones in your pocket
reliably notice each other over Bluetooth in the background?* iOS is famously
stingy about that. So the very next step isn't "build the app," it's a tiny
two-phone spike to get a real go/no-go before betting on it.

**💡 ideas / where it's headed** — the de-risk spike → the iOS client (detect +
upload + a Wrapped screen) → fun group analytics ("your 2am person," "your third
place," biggest group hang). The dream is a wholesome friendship-Wrapped you
actually look forward to.

### How it got here

- **Engine + simulator (done):** sightings → sessions → Wrapped, fully tested.
- **Backend (done):** FastAPI auth, groups/invites, session ingest (shared-group
  + duplicate reconcile), Wrapped API — reuses the engine, tested via TestClient.
- **iOS de-risk spike (next):** two phones, background co-presence — go/no-go.
- **iOS app:** detect-and-upload client + Wrapped screen.

## Tests

```bash
python -m pytest -q
```
