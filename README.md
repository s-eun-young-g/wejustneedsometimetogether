# we just need some time together

How much time do you actually spend *with* the people you care about — and where?
TT records co-presence: when you and someone in your group are physically
together, it logs the time and place, then turns it into a "Wrapped."

**It's a co-presence recorder, not a location tracker.** TT never needs to know
where you are when you're alone — only the time and place you spend *with* someone
who's also in your group and opted in. That principle drives the whole design.

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

## Roadmap

- **Engine + simulator (done):** sightings → sessions → Wrapped, fully tested.
- **Backend:** auth, groups/invites, session ingest, Wrapped API.
- **iOS de-risk spike:** two phones, background co-presence — go/no-go.
- **iOS app:** detect-and-upload client + Wrapped screen.

## Tests

```bash
python -m pytest -q
```
