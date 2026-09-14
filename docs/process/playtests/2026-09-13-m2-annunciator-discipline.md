# Playtest — 2026-09-13 (M2 increment 6: annunciator discipline and QRH v1)

Build: working tree at the increment-6 gates (green) · Duration: ~25 min ·
Mode: teletype · Players: maintainer solo (with an agent at the keyboard),
QRH read as a player for the first time

## Setup

Second session today, and a deliberate rerun of this morning's failure. The
increment exists because of one paragraph in the particle-event note: the
crew shed a terminal on purpose, the lamp for it lit, and when the *essential*
terminal latched up underneath that lamp the panel said nothing at all.

Two runs on TB-1, both starting with a lamp test (which is now step 1 of the
cold & dark checklist, as the QRH claims it is):

- **Run A — `core:spe-minor`, seed 99.** The exact scenario that produced the
  finding. Shed, acknowledge, hold, and see whether the second casualty
  announces itself this time.
- **Run B — injected stuck-dominant, quiet environment.** QRH 42-01 walked by
  hand, top to bottom, to see whether a five-step stabilization checklist is
  actually worth the page it costs.

## What happened

**Run A — the silence is gone.** SEU HAZARD at 84.1 s, acknowledged. CB A2
open at 97.6 s, `DATA BUS A DEGRADED` raised and acknowledged — and the panel
went *steady*:

```
MASTER CAUTION: ACTIVE — DATA BUS A DEGRADED, SEU HAZARD
   CAUTION   DATA BUS A DEGRADED
   CAUTION   SEU HAZARD
```

Then at 121.0 s, with no prompting and nothing new on screen to look at:

```
* [   121.0s] WARNING   DATA BUS A FAILED RAISED
```

and the recall list ranked it above the two cautions the crew already knew
about, with the `!` marking it as the only unseen thing on the panel. That is
the whole increment, in one line of a flat-line terminal. This morning the
same event produced nothing.

**Run B — the QRH is worth its page, barely.** Injected stuck-dominant on
RT 12 with the bus healthy. Both lamps raised on the same tick, ranked
correctly, and a single `sys.annunciator ack` took both ("2 acknowledged").
Steps 2 through 5 took about fifteen seconds of sim time and produced exactly
one useful thing the FIM would not have: the instrument panel with two lines
marked `? STALE` at 4.4 s, which is the moment a player understands that the
cabin ammeter in front of them is a photograph. Step 5 (read the flux, for the
log) read 0.111 p/cm²·s — background, so this board is a suspect and not a
weather victim, which is precisely the sentence FIM 42-11 §4 needs and which
nobody would have thought to capture without being told.

Then the hand-off, and the session's surprise: cycling CB A2 per FIM 42-11 §3
made `DATA BUS A FAILED` **clear on the spot** while `DEGRADED` stayed lit.
The verdict announced itself. Up to now "the bus recovers the moment the
babbling terminal goes dark" was something you read off a table; it is now a
lamp going out while your hand is still on the breaker.

## Friction list

1. **`wait` does not break on a new warning.** In run A the warning was raised
   at 121.0 s and printed inside the output of a `wait 120`, where it scrolled
   past with 90 seconds of sim time still to run. On a real ship the master
   warning interrupts what you are doing. The teletype should abort a `wait`
   on any new warning-severity raise and say why. Filed to the M2 list; it is
   a client change, not a model one.
2. **The QRH tells you to note the flux and gives you nowhere to note it.**
   Step 5 is a read with no destination. The FDR has it, but the crew's own
   log — the thing FIM 42-11 §4 actually asks them to write — is the LOG
   station's notebook, which has no write verb yet. Filed with the LOG work.
3. **The error-count column misaligns past 999.** `NO RESPONSE (1224x) 1226`
   pushes the count column one character right. Cosmetic, filed, not fixed.

## Surprise list (emergent-behavior ledger)

- **A clearing warning is a diagnosis.** Nobody designed the FIM 42-11 §3
  verdict to be annunciated; it fell out of grading the same telemetry at two
  thresholds. The cheapest new affordance of the session, and the one most
  likely to change how players work the tree.
- **Two lamps on the same tick reads better than one.** DEGRADED and FAILED
  raising together (run B) looked, briefly, like a bug — until the recall list
  made the point that they are two separately true statements about the same
  measurement. The instinct to collapse them into one lamp is worth resisting.
- **The lamp test at step 1 changes the feel of cold & dark.** Every lamp lit
  and then dark again, before the battery is even on, is the first thing the
  ship does in a session now. It costs two seconds and it makes the panel feel
  like hardware.

## Manual-bar observations

- QRH 00-00 §3 ("a lamp that is already lit will not light again") was written
  from this morning's finding and is the page that explains the graded lamps.
  It reads as a warning about the ship, which is correct.
- QRH 42-01's five steps were walkable from memory after one read. The
  ordering test — ack first, then *is the controller alive*, then *what have
  you lost*, then *what caused it* — held up.
- **Revision wanted:** QRH 00-00 §5's index is a two-row table with one entry.
  It will not scale and it should not be hand-maintained; when QRH 24-01 lands
  the index should be generated from the procedure set like the WDM tables.
- SOM 24-30-01 and 24-30-03 both gained a lamp-test step 1, so every step
  reference in the binder shifted by one. Caught by grep, not by CI. A check
  that manual prose and procedure step numbers agree is worth having before
  the binder gets much bigger.

## Keep/kill calls

- **Keep:** two masters rather than one. The warning/caution split did real
  work in both runs and cost one property.
- **Keep:** acknowledge-does-not-clear. The temptation to let `ack` drop a
  lamp is strong and would have silently reintroduced the exact defect this
  increment exists to fix.
- **Kill:** nothing this session.
