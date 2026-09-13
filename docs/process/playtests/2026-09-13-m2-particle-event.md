# Playtest — 2026-09-13 (M2 increment 5: the stress model and the particle environment)

Build: working tree at the increment-5 gates (green) · Duration: ~30 min ·
Mode: teletype · Players: maintainer solo (with an agent at the keyboard),
SOM 42-30-02 read as a player, first session with a scenario driving the sim

## Setup

Two runs on TB-1, both from cold & dark through the EPS start and the DB-A
checkout, then a solar particle event supplied by content rather than by an
injection console. Nothing is scripted to break in either scenario: the only
inputs are a flux timeline and a seed, and whether a terminal latches up is
the stress model's business.

- **Run A — `core:spe-minor`, seed 24.** 250 p/cm²·s for about four minutes.
  The case the checklist was written for.
- **Run B — `core:spe-transit`, seed 1553.** 4000 p/cm²·s for ten. The case
  the checklist survives rather than solves.

The thing under test is whether an emergent casualty is *legible*: whether the
crew is warned, whether the trade in 42-30-02 is understandable while it is
being made, and whether the cause of a latch-up is recoverable afterwards from
what the ship shows rather than from what the author knows.

## What happened

**Run A — the event the procedure is for.** Cruise was quiet at 0.11 p/cm²·s.
At 84.1 s the panel raised SEU HAZARD on its own, three quarters of a minute
before anything else happened, and `data.seu read` gave 161 p/cm²·s. Working
42-30-02: CB A2 open at 99 s, DATA BUS A DEGRADED annunciated 0.9 s later —
expected, and the lamp the procedure warns will now be lying about the ship's
health. Held the configuration through the peak (249.99 p/cm²·s at 220 s),
watched the flux come back down, and SEU HAZARD cleared itself at 312.2 s.
CB A2 closed; DEGRADED cleared at 340.5 s; `data read` showed 2/2 healthy.
Six minutes, one decision, nothing broken. The event was survived by giving
something up on purpose and then taking it back.

**Run B — the event the procedure does not solve.** SEU HAZARD at 66.1 s,
flux 145 and climbing an order of magnitude every ninety seconds. Same shed at
69 s. Then the thing this increment exists for: at 341.6 s, with the flux
pegged at 4000, **RT 5 — the terminal that cannot be shed, because it is on
the essential bus — latched up**, and *the panel did not say a word*, because
DATA BUS A DEGRADED was already lit from the shed the crew had performed
themselves. The casualty arrived underneath a lamp that was already on.

It was found by reading the table at 370 s:

```
  RT   STATE             ERRORS
  12   NO RESPONSE (3015x) 3017
  5    NO RESPONSE (288x)   289
```

— two terminals dark, one of them deliberately, with the error counts carrying
the difference in age. `eps read` had the same news in a second voice: the
avionics ammeter, carried by RT 5, had gone `? STALE` at 29 s old while the
cabin ammeter behind the shed terminal sat at 301.7 s. Two instruments dead
for two entirely different reasons, and both readable.

Cycled CB E3 (FIM 42-11 §3): RT 5 answered again. Restored CB A2. Bus whole at
576 s, with the flux still at 2674 p/cm²·s — which, per the checklist, is a
mistake; see friction.

## Friction list

1. **The player restored a terminal in the middle of the event.** 42-30-02
   step 5 says hold until the flux falls back through 100 p/cm²·s and the
   player closed CB A2 at 2674, having just recovered RT 5 and being pleased
   about it. The checklist was right and was not consulted at that moment.
   Won't fix in content — this is what the procedure is *for*, and the sim
   punished it correctly by leaving both boards exposed. Worth watching
   whether crew-AI advisories (M3) should call the read-back.
2. **A shed terminal accumulates error counts.** RT 12 came back from a
   planned shed reading `12   OK   2417`, so the counter that FIM 42-11 uses
   to age a casualty is now dominated by an event the crew caused on purpose.
   The bus controller genuinely cannot tell a shed terminal from a dead one,
   so the count is honest — but a crew reading the table after the event has
   no way to net it out. Filed as an M2 loose end: the table wants a way to
   mark a terminal as *shed by command* (the breaker position is known to the
   ship even if it is not known to the BC).
3. **`wait` is the only clock.** Riding out a ten-minute event through a
   teletype means typing `wait 120` four times. Time compression is specified
   (ADR-0002: more ticks per wall second, never a bigger dt) and unbuilt;
   this is the first session where the absence was actually felt.

## Surprise list (emergent-behavior ledger)

- **The second casualty hid under the first lamp.** 42-30-02's preamble warns
  that a casualty arriving under an expected DEGRADED will be harder to see;
  it happened on the first severe run, unprompted, and the warning turned out
  to be an understatement. The lamp is not "harder to see" — it is *silent*.
  This is the strongest argument yet for the QRH caution-priority work and for
  something in the panel that distinguishes "degraded as configured" from
  "degraded, new".
- **The stale ammeter beat the bus table to the news.** The increment-4 work
  turned out to be the faster indication: RT 5's transducer went stale 29 s
  before the crew read the table, and on a panel-watching player it would have
  been the first sign. Two unrelated increments produced a cross-check nobody
  designed.
- **A dark ship rides out any flux untouched.** Falls out of `needs_rail`
  with no special-casing, and it makes the cold & dark state a *tactic* rather
  than just a start condition. Noted for the M3 mission design.

## Manual-bar observations

- SOM 42-00-00 §9–§10 carried the whole run: the player never needed to know
  what a hazard rate is, only that flux is a number, 100 is the line, and an
  unpowered board cannot latch up.
- 42-30-02's table of which terminals to keep and shed was read once and used
  twice. The BC row ("shed the controller and you are blind, not safe") is the
  line that stopped the player from protecting the controller in run B.
- **Revision wanted:** 42-30-02 §3 tells the crew what to do when a kept
  terminal latches, but nothing tells them to *look*. The procedure holds on
  the flux monitor for up to ten minutes and never says "read the bus table
  while you wait". Add a monitoring instruction to the hold step.
- FIM 42-11 §4 (read the environment before you write the log) was met in
  anger for the first time and did its job: 4000 p/cm²·s at the time of the
  casualty makes RT 5 a weather victim, not a suspect board.

## Keep/kill calls

- **Keep:** scenarios as content. The two runs differ by one YAML file and a
  seed, and the second one taught something the first could not.
- **Keep:** the unconditional per-tick draw. Run B's replay is bit-identical
  with and without the crew's shed, which is the property that makes "watch
  what I did" worth building at all.
- **Kill:** nothing this session.
