# Playtest — 2026-09-13 (M2 increment 7: MAINT v1 — the board swap)

Build: working tree at the increment-7 gates (green) · Duration: ~35 min ·
Mode: teletype, scenario-driven · Players: maintainer solo (with an agent at
the keyboard), MAINT 00-00 and 42-110-001 read as a player

## Setup

Two runs on TB-1, both `core:spe-transit` seed 1553 — the same severe event
that produced the increment-5 and increment-6 findings, deliberately reused so
the three sessions are comparable. Cold start, DB-A checkout, then the weather.
Nothing is scripted to break: RT 5 latches up on its own at 341.6 s both times.

- **Run A — the whole loop.** Flux → warning → jam → QRH 42-01 → FIM 42-11 →
  MAINT 42-110-001. The M2 acceptance vignette, walked by hand.
- **Run B — the trap.** Same casualty, but pull the babbling board instead of
  cycling its feed, fly on one terminal, and find out what happens when the
  second one goes and the shelf has one item on it.

The thing under test: whether a verdict can now be *acted* on, and whether the
ship is honest about the hole you leave in it.

## What happened

**Run A — a verdict with somewhere to go.** SEU HAZARD at 66.1 s, 208 p/cm²·s.
The bus jammed at 341.9 s and both lamps came up together. QRH, then FIM 42-11:
CB A2 cycled with no effect, CB E3 cycled and `DATA BUS A FAILED` cleared on
the spot — verdict RT 5, exactly as in the previous two sessions. The new part
starts here. `data.db.a.rt.5 records` named the board on the ship rather than
in the abstract:

```
rt.5: 42-110-001/0002 — Data bus remote terminal, 1553 family
   P/N 42-110-001   position rt.5   hours 0.10 h
   MET 000:00:00:00.0  fitted     rt.5
```

`maint read` said one on the shelf. Tried `remove` on the live bus first, on
purpose, and got sent away citing MAINT 42-110-001 §2. Three breakers open, one
second to bleed, and then the swap read the way it should: `/0002 removed —
position open`, the position answering `NOT FITTED`, and `/0003 installed from
stores — verify (SOM 42-30-01)`. Re-energized in checkout order; DB-A HEALTHY;
stores `NO SPARES`. Six commands of real work, and at the end the ship could
tell me which board was in the rack and how long it had been running (0.00 h),
which it could not do this morning.

**Run B — the trap works.** Same jam, but this time I de-energized and pulled
RT 5 rather than cycling it. The bus came back **DEGRADED with RT 12 OK**: the
jam is genuinely gone, because there is no board in there to babble. That is
the first time a maintenance action has been a *tactical* option, and it felt
like one — cheaper than the FIM tree and strictly worse than it.

Then the event kept going, and at 407.5 s RT 12 latched too. `DATA BUS A
FAILED` again, and now the accounting bites: one spare, two open questions.
Swapped RT 12 with it; `data.db.a.rt.5 install` refused — *no 42-110-001 in
stores* — and the stores sheet ended the session reading NO SPARES, two units
on the bench, and RT 5's position open since MET 5:54. Nobody told me RT 5 was
out. That is the design working, and it is uncomfortable in the right way.

## Frictions

1. **The error counters survive the board. (real gap)** After the swap, the bus
   table read `5  OK  170` — a hundred and seventy errors against a unit that
   was on a shelf when they were counted. The counters belong to the
   controller's ledger for that address, which is defensible, but a maintenance
   action with no way to zero them means SOM 42-30-01's "errors 0" close-out is
   unreachable for the rest of the flight. Real analyzers have a counter reset;
   this one needs one, gated so it is a deliberate act that the FDR records.
2. **The task is printed for RT 12 and NOTE 2 does the rest.** Playing it for
   RT 5 meant substituting an address and a breaker by hand in an otherwise
   executable checklist. It worked, and the note is honest, but a checklist you
   have to edit while you read it is a checklist you can get wrong at 4 a.m.
   Procedures need a target parameter before there are eight terminals.
3. **Not every fitted unit has an address to read its nameplate at.** The
   generated IPC lists a serial for the battery, the loads, every breaker — but
   `records` only reaches positions with an SCL address, and `bat1` has none.
   The catalog promises identity the ship cannot show.
4. **`wait` still does not abort on a new warning.** Run B's 60 s wait spanned
   the second latch-up entirely; the annunciation scrolled past mid-wait. Third
   session in a row this has cost something. It is on the list; it should move
   up it.
5. **Removal records why nothing.** The board came off after the power cycle
   had already cleared the latch-up, so what the FDR recorded was *no fault
   found* — true, and useless to the next person. The chain is reconstructable
   (the `fault-onset` at 341.9 s names rt.5), but only from the FDR, and the
   crew still has no way to write "pulled per FIM 42-11 verdict" against the
   serial. The LOG notebook write verb would close this and the increment-6
   finding at once.

## What went in because of the session

Nothing was changed mid-session; all five frictions are filed rather than
fixed. The counter reset (1) and the procedure target parameter (2) are the two
that block scaling this to a ship with more than two terminals, and both are
now on the M2 list.

## Verdict

The loop closes. From a number on a monitor to a different serial in the rack,
with an instrument confirming the function at the end, and every fact along the
way read off a panel, a table, or a refusal. The two things that make it a
*game* rather than a chore both showed up unprompted: pulling the board is a
real tactical choice with a real cost, and the shelf running out turns the
second casualty of the same event into a decision instead of a formality.
