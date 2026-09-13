# Playtest — 2026-09-12 (M2 increment 4: sensor transport and stale readings)

Build: working tree at the increment-4 gates (green) · Duration: ~25 min ·
Mode: teletype · Players: maintainer solo (with an agent at the keyboard),
binder read as a player, FIM 42-14 met for the first time

## Setup

Second session today; the increment landed the same day it was specified, so
this one is on time rather than overdue. Two runs on TB-1, both from cold &
dark through SOM 24-30-01 and the SOM 42-30-01 checkout, then a casualty the
player was not told about. The thing under test is the new symptom: an
indication that stops being refreshed because its terminal stopped answering,
and the section that decides whether that is a data fault or a real one.

The scenario side gained one affordance for run 2 — an off-screen action, so
a breaker can move without the player being the one who moved it. Faults and
off-screen actions are both announced to the transcript as `[scenario: ...]`
and never to the player.

## What happened

**Run 1 — a dead terminal, worked from the gauge.** `dead` on RT 12 with the
bus healthy. Three seconds later the panel carried two facts at once: DATA BUS
A DEGRADED, and one measurement line out of seven marked `? STALE` with its
age at 3.1 s while the other six read 0.1 s. Working FIM 42-14 §3 in order —
cabin ammeter stale, BUS A 26.17 V, CB A1 CLOSED, then the bus table — put the
verdict on RT 12 in four readings, and handed off to FIM 42-11 §2 for the
repair. The panel reading the whole thing off one screen is new; up to now a
casualty was a lamp plus a table, and the instruments were all equally alive.

**Run 2 — the trap.** The tie opened off-screen. BUS A collapsed to −0.06 V,
which took RT 12 with it, which froze the cabin ammeter — at **4.954 A**,
the last honest value, a perfectly healthy-looking cabin load on a bus that is
dead. Both cautions lit together (BUS A UNDERVOLT and DATA BUS A DEGRADED) and
the data lamp is the louder-looking of the two, because a bus undervolt with
the ship otherwise running reads like an instrument problem while DEGRADED
reads like a system problem.

The discipline held because the section makes the cheap check first: the
ammeter is carried, the voltmeter is not, and the voltmeter said −0.06 V. That
is the whole increment in one reading pair.

**The one I could not stage.** A controller power loss takes *every* carried
indication stale with **no** annunciator at all — the lamp cannot fire because
nothing is reporting. It is covered in conformance (FIM 42-14 walks to step 6)
but it needs the BC fault modes to be stageable as a blind scenario rather
than as a breaker somebody opened. Noted for the BC/firmware increment.

## Friction list

1. **Two cautions, no priority.** `MASTER CAUTION: ACTIVE — BUS A UNDERVOLT,
   DATA BUS A DEGRADED` lists in blueprint order, which in run 2 happened to
   put the correct suspect first by luck. A crew with three lit and a
   30-second budget needs the panel to say which one is upstream of the
   others. *Not a defect; scope evidence for the QRH increment, which is
   where "work this one first" belongs.*
2. **The age column is doing a lot of work in a small font.** In teletype the
   `? STALE` tag carries it, and that reads clearly. On the panel it is `?`
   plus dim plus a 4-character age field, and during run 1 the eye went to the
   annunciator first every time. The information is present and correct;
   whether it is *loud* enough is a station-layout question, not a model one.
   Watch it at the MAINT increment when the panel gains competition.
3. Nothing else. The tree asked for four readings and gave a verdict.

## Surprise list (emergent-behavior ledger)

- **A frozen gauge is more dangerous when it is right.** Run 2's 4.954 A was
  not a wrong number — it was a true number about a moment that had passed.
  Nothing designed that; it falls out of "keep the last item and let it age".
  It is also the first casualty in this project where the honest response to
  an instrument is to distrust it, and the manuals had to grow a rule
  (42-00-00 §8) that says so out loud.
- **The lamp going quiet is itself a symptom.** Killing the controller after
  DEGRADED had latched drops the caution — correctly, since nothing is
  watching — and the dark lamp now means *less* than it did a second earlier.
  The sim said this in prose (SOM 42-00-00 §6) for two increments before it
  was true; it is true now, and seeing a caution clear because the ship went
  blinder is a genuinely unsettling half-second.

## Manual-bar observations

- FIM 42-14 §2's rule — *panel-wired indications cannot go stale* — is the
  sentence that makes the section work. Without it the tree is four arbitrary
  readings; with it, every step is obviously in the right order.
- SOM 42-00-00 §8's table (which reading is carried by which terminal) was
  consulted in both runs and is the page the binder opens to. It belongs in
  the generated WDM sheet too, and now is: the instrumentation table grew a
  **Reported via** column, so the wiring sheet says which readings can freeze.
- The §1 framing in 42-14 ("the reporting chain, or the measured system") is
  what stopped run 2 going into the data system. That framing, not the
  checklist, is the content.

## Keep/kill calls

- **Keep**: showing the stale value instead of blanking it. Blanking would be
  kinder and would delete the entire lesson; the age tag is the honest form.
- **Keep**: one staleness horizon for the panel, the printed line, and the
  monitors. During the review pass these were two constants that happened to
  agree; a reading the panel dims must be a reading the caution system stops
  trusting, and that is now one number.
- **Keep**: sampling the sensor every tick even when nothing can deliver it.
  It costs a noise draw and it buys replay that does not depend on bus state.
- **Open for the next increment**: caution priority (friction 1), a blind way
  to stage a controller loss, and the panel-legibility question in friction 2.
