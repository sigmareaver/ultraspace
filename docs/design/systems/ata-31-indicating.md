# ATA 31 — Indicating & Recording

Status: Draft v0.1 (M2 increment 6 implementation contract) · Last updated: 2026-09-13 · Owner: design+engineering
Related: [../ui-presentation.md](../ui-presentation.md), [../manuals-as-gameplay.md](../manuals-as-gameplay.md),
[../failure-and-repair.md](../failure-and-repair.md), [ata-42-data.md](ata-42-data.md),
[ata-24-eps.md](ata-24-eps.md)

Chapter 31 is the ship's **attention budget**. Every other chapter produces
facts; this one decides which of them reaches a human, in what order, and how
loudly. It is the smallest chapter in the binder and the one most likely to
decide whether a casualty is survived.

This revision specifies **increment 6** — annunciation severity, the
new-versus-acknowledged distinction, graded annunciation, and QRH v1 — and
marks the rest **(later)**.

## 1. Why this exists (the playtest that wrote this page)

From the 2026-09-13 particle-event playtest, run B:

> The crew shed RT 12 per SOM 42-30-02, which lit `DATA BUS A DEGRADED` — an
> expected lamp, for a degradation they chose. Four and a half minutes later
> the *essential* terminal latched up and the bus went to zero terminals. **The
> panel said nothing**, because the lamp was already on and a lamp does not
> light twice.

Three separate defects hide in that paragraph, and they are the scope of this
increment:

1. **No severity.** Losing one terminal of two and losing the bus entirely
   produced the same amber word. A crew cannot triage what the panel refuses
   to rank.
2. **No graded annunciation.** `health < 1.0` is one predicate covering a
   spectrum. The second casualty was *inside* an already-true condition.
3. **No new-versus-seen.** Nothing on the panel distinguished "this lamp has
   been lit for four minutes and you know about it" from "this just happened."

The fix is old, boring and from the cockpit: rank alerts by severity, give the
important transitions their own annunciation, and make the master lights
*attention-getters that reset* rather than a summary that latches.

## 2. Severity (three levels, no more)

| Level | Glyph | Color | Meaning | Crew obligation |
|---|---|---|---|---|
| `warning` | `▲` | red | Immediate hazard to the ship or the mission | Act now; QRH, this minute |
| `caution` | `▲` | amber | A real abnormality with time to think | Act soon; QRH before it compounds |
| `advisory` | `●` | cyan | Awareness; a configuration worth knowing | Note it; no action implied |

Colorblind-safety is preserved by redundant glyph *and* by a spelled severity
word on every text surface — the teletype has no color at all, and it must
carry the same information (ui-presentation.md).

Severity is declared per annunciator in ship content (`severity:`), defaults to
`caution`, and is a **content decision reviewable in a diff**. A chapter that
declares everything a warning has declared nothing.

**Master lights.** Two, not one: `MASTER WARNING` if any warning-severity lamp
is active, `MASTER CAUTION` if any caution-severity lamp is active. Advisories
never drive a master light — that is what makes them advisories.

## 3. New versus acknowledged (the attention-getter contract)

Every lamp carries two bits, not one:

- `active` — the monitored condition holds *now* (unchanged from M1: measured
  values only, `TelemetryStore.fresh`, a stale source is a silent source).
- `acknowledged` — a human has seen this particular onset.

Rules:

1. A lamp raised is `active`, **not** `acknowledged`. It is **NEW**.
2. `sys.annunciator ack` acknowledges every active lamp. It does **not**
   clear them: the lamp stays lit, steady, for as long as the condition holds.
   Acknowledging is saying *I have seen this*, never *this is fine*.
3. A lamp that clears and re-raises is NEW again. The crew is told twice
   because it happened twice.
4. The master lights are **attention-getters**: they flash while any lamp of
   their severity is NEW, and go steady once acknowledged. A steady master is
   not a clear master.

This is the whole fix for defect 3, and it is deliberately cheap. The expensive
version — aural alerts, inhibit logic by flight phase, a separate recall
button — is **(later)**.

## 4. Graded annunciation (the fix for defect 2)

An annunciator is a predicate on one measured value. When a system can be *more*
broken than the predicate can express, the content owes the crew a second
annunciator at the harder threshold, at a higher severity.

DB-A is the worked case, and ships in this increment on both vessels:

| Lamp | Predicate (BC health fraction) | Severity |
|---|---|---|
| `DATA BUS A DEGRADED` | `< 1.0` — any terminal declared FAILED | caution |
| `DATA BUS A FAILED` | `< 0.01` — no terminal answering at all | warning |

Now the playtest's silent casualty raises `DATA BUS A FAILED` as a NEW warning
while `DEGRADED` stays lit and acknowledged underneath it. The panel says two
true things at once, ranked, which is exactly what happened to the ship.

**Rule for content authors:** overlapping predicates are correct and expected.
The panel is not a partition of the state space; it is a set of statements
about it, each of which is separately worth a human's attention.

**Rule for the systems that grade:** a system display that has its own word
for its condition must use the *same* grade the panel uses. `DATA BUS A
FAILED` lit over an analyzer still calling the bus DEGRADED teaches a player
to trust neither, so `DataBus.state_word()` is one function
(HEALTHY / DEGRADED / FAILED) feeding both surfaces. Found in play,
2026-09-13.

**Not in this increment:** the bus table still cannot say a terminal was shed
*by command* rather than lost, so a planned shed and a casualty read the same
on the analyzer (playtest finding, 2026-09-13; the breaker position is known to
the ship and could say so). Tracked on the M2 list.

## 5. The panel as a fixture (`sys.annunciator`)

The annunciator panel becomes addressable. It is a **fixture**, not yet a
device: it has an SCL address and verbs but no electrical ports, exactly the
transducer fiction M1 used, and for the same reason — the honest version needs
a power feed and a lamp that can burn out, and that is a separate increment.

```
sys.annunciator read   # the recall list, ranked
sys.annunciator ack    # acknowledge every active lamp
sys.annunciator test   # lamp test: hold every lamp lit for 2 s
sys read               # system-level summary = the recall list
```

**Recall ordering** (`read`) is the increment's most consequential decision,
because it is the order the QRH tells the crew to work in:

1. Severity first: warnings before cautions before advisories.
2. Within a severity, **NEW before acknowledged** — the thing that just
   happened outranks the thing you already know about.
3. Within that, blueprint order, which is chapter order, which is stable.

Not recency. A panel that sorts by time teaches the crew to work the newest
problem rather than the worst one, and the newest problem is very often a
*consequence* of the worst one.

**Lamp test** lights every lamp regardless of condition for 2 s, then releases.
It is a real procedure step (cold & dark, before anything else) and it exists
now so that the increment which makes lamps fail has somewhere to fail *to*.
While a test is running, the panel reports it; a test does not acknowledge
anything and does not raise FDR alert events.

## 6. FDR

Unchanged kinds (`annunciator-raise`, `annunciator-clear`) gain `severity` in
the payload. New kinds:

| Kind | Source | Payload |
|---|---|---|
| `annunciator-ack` | `sys.annunciator` | `{count, messages}` |
| `annunciator-test` | `sys.annunciator` | `{lamps}` |

The journal records that the crew was told and that the crew answered. A
casualty review that shows a warning raised and never acknowledged is a
finding about the crew, not about the ship — and that is a thing the log
should be able to say.

## 7. QRH v1

The Quick Reference Handbook is the third executable manual, and its job is
different from the other two (manuals-as-gameplay.md): the SOM is *how the
ship is operated*, the FIM is *which part is broken*, the QRH is **what to do
in the next sixty seconds**. It stabilizes; it does not diagnose. Every QRH
checklist ends by handing off — to a FIM task, to an SOM configuration, or to
"monitor and continue".

Increment 6 ships:

- **QRH 00-00 — Using this book.** The priority rule (work the panel in
  recall order; warnings before cautions; NEW before acknowledged), the
  acknowledge discipline (ack early — an unacknowledged lamp is the only way
  the panel can tell you about the *next* one), and the index. Not executable:
  it is the page you read once, before anything is wrong.
- **QRH 42-01 — DATA BUS A FAILED.** Executable. Confirms the controller is
  alive (a dead controller is a different page), reads the flux because the
  answer changes the prognosis and not the actions, and hands off to FIM 42-11
  §3. Roughly five steps, and it must be shorter than the FIM task it hands
  off to — if a QRH checklist is long, it is a FIM task wearing the wrong hat.

**(Later M2)** QRH 24-01 (bus undervolt), QRH 31-01 (multiple annunciations — the
executable form of the priority rule), MEL cross-references.

## 8. Conformance obligations

- Every ship's annunciator set loads with a valid severity, and every
  annunciator that can reach a `warning` state has a QRH page or a documented
  reason it does not. (v1: enforced by review; mechanical check when the QRH
  index is complete.)
- QRH 42-01 passes headlessly against a jammed bus, and takes its
  controller-dark branch against an unpowered BC.
- A casualty test proves the increment's whole point: with `DATA BUS A
  DEGRADED` already lit *and acknowledged*, the loss of the remaining terminal
  raises a NEW warning and re-flashes the master. This test is the playtest
  finding, frozen.
- Determinism: acknowledgement is a command like any other, journal-recorded,
  and replays.

## 9. Not in this increment

- The panel as a **powered device** (dark at cold & dark — the honest "alarm
  reset"), and lamps that burn out. Both need §5's fixture to become a device.
- Aural alerts and inhibit logic.
- Per-chapter tiles (`ELEC`, `DATA`…) in the TUI annunciator row; v1 keeps one
  tile per lamp plus the two masters.
- Crew-AI reading the panel aloud (M3).
