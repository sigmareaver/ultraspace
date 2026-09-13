# Playtest — 2026-09-12 (M2 increments 2–3: the fault model and the harness tree)

Build: 8eedd70 · Duration: ~40 min · Mode: teletype · Players: maintainer solo
(with an agent at the keyboard), binder read as a player, no source consulted
during the runs

## Setup

Overdue note: increments 2 (fault model v1, 2026-07-19) and 3 (harness depth,
2026-07-20) both landed without one, against workflow.md's weekly cadence and
its DoD item 4. This session covers both, on TB-1, in teletype — the
accessibility floor and the surface where the manuals have to carry the whole
load, since there is no panel to look at.

Intent: play the U4 story end to end, then work a *medium* fault the same way,
driving both from the binder (SOM 24-30-01, SOM 42-30-01, FIM 42-11, FIM
42-12) rather than from the conformance runner. Faults were injected by the
scenario side and never announced.

## What happened

**Run 1 — cold & dark to a healthy bus.** Nine commands from SOM 24-30-01,
then the SOM 42-30-01 checkout order (terminal feeds, then the controller).
Bus came up `HEALTHY`, both terminals `OK`, zero errors. One self-inflicted
detour, below.

**Run 2 — the U4 latch-up.** `stuck_dominant` on RT 12 while the bus was
healthy. The annunciator raised 0.3 s later and the table showed the jam
signature honestly: *both* terminals `NO RESPONSE`, ten misses each, declared
within a tenth of a second of each other — exactly what FIM 42-11 §3 says to
split on, and not what a "RT 12 is broken" reading of the story would predict.
Cycling CB A2 (open, hold 1 s, close) cleared it on the first try; DATA BUS A
DEGRADED cleared on the tick the feed came back. Error counters kept the
episode: 22 against RT 12, 11 against RT 5 — the innocent terminal wears the
jam's scars too, which is the right kind of honest.

**Run 3 — a shorted coupler (J2), worked blind.** Table showed all-dark, so
FIM 42-11 §3 first: cycled both terminal feeds, nothing recovered. That is the
documented hand-off, and it lands on FIM 42-12 §3. De-energized all three
breakers, waited for the bleed, and probed:

```
> data.db.a.j1 read
j1: db.a coupler — DMM across the pair (bus de-energized)
  seg.bc-j1 (toward bc.a): 78.0 ohm
  seg.j1-j2 (toward j2): 0.0 ohm
  stub.j1-rt5 (toward rt.5): 2.1 ohm
```

Clean toward the controller, dead short toward J2: the fault is in the J1–J2
interval, and §3 step 5 says ohms cannot tell the run from the coupler at its
end. Replaced the run, re-energized — still dark. Back to de-energized,
replaced coupler J2, re-energized: `HEALTHY`, both terminals answering, 68
errors each left standing as the evidence trail.

That failed first guess is the best thing in the session. The checklist
predicted it, priced it (a wasted run), and told me what to take next; nothing
about it felt like the sim scoring a point off me.

## Friction list

1. **A refused verb taught nothing.** Guessed `eps bus.a.precharge close`
   (the SOM says START). The refusal was `verb 'close' not supported` — full
   stop — so I moved on to the tie, into a dead BUS A, and ate the inrush
   trip. The trip message is the counter-example done right: it cites SOM
   24-00-00 §3. **Fixed this session** (51a92bd): refusals now offer the
   device's vocabulary, `(try: start, stop, read)`, with a regression test.
2. **The de-energize dance is eight commands of ceremony, twice.** Three
   breakers plus a bleed wait, then the same again after the failed first
   replacement. Correct, and the interlock is the point — but it is the
   strongest argument yet for SCL scripts (command-language.md) to arrive
   with MAINT, so a checklist step can be one typed line. *Not filed as a
   defect; recorded as scope evidence for the MAINT/QRH increment.*
3. Nothing else. The binder answered every question I brought to it.

## Surprise list (emergent-behavior ledger)

- **The jam implicates the innocent.** RT 5's error counter climbs during RT
  12's latch-up, so after the repair the table shows two terminals with
  matching damage and no way to tell victim from culprit — only the FDR
  ordering does. Unauthored, physically right, and a genuinely good hook for
  MAINT's records.
- **A coupler cannot show you its own break.** Fell out of the model's own
  geometry rather than being designed in: an open feed-through reads clean
  from the coupler standing on it and OL from the next one down. The review
  found the tree had not been taught this (see below); it is now the
  discriminator FIM 42-12 §2/§3 turns on, and it makes the DMM feel like an
  instrument with a point of view instead of a truth oracle.

## Manual-bar observations

- FIM 42-11 §3's insistence that the jam signature is *all* terminals dark,
  declared together, is what made run 2 readable. Without it the annunciator
  plus a table of two dead terminals reads like "the bus is gone".
- FIM 42-12 §3's cost-order ladder (replace the run, verify, then the
  coupler) is the section that carried run 3. It needs the §4 reminder that
  replacing hardware tells you nothing by itself — which is now true of the
  sim as well as the prose (13ce571).
- **Sections rewritten this session** after the review found the tree
  convicting innocent parts on coupler faults (cf376d3): FIM 42-12 §2 (the
  coupler check before the module goes), §3 (both-ways-zero, the
  neighbour-side OL, the interval ladder), SOM 42-00-00 §2 and §5 (the
  asymmetry, and what the meter cannot say).

## Keep/kill calls

- **Keep**: the de-energize interlock on both the DMM and `repair`. It costs
  eight commands and buys the entire diagnostic culture.
- **Keep**: error counters that never rewind. The post-repair table reading
  68/68 is a better souvenir than any log line.
- **Changed**: `repair` no longer refuses on a sound part (13ce571). The old
  refusal was a free verdict — it told the player the part was good, which no
  reading had. Replacing a good run is now allowed, wasteful, and silent.
- **Open for the next increment**: the ceremony in friction 2, and FIM 42-13
  (the controller is now the only harness-tree exit left).
