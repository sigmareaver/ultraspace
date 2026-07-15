# Game Overview

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design
Related: [../vision.md](../vision.md), [failure-and-repair.md](failure-and-repair.md),
[human-element.md](human-element.md), [scenarios-and-campaign.md](scenarios-and-campaign.md)

## Player role

The player is the **systems officer** (and, early game, sole engineer) of a small working
vessel. Piloting exists but is procedural, not twitch: burns are planned, clearances
requested, autopilot modes armed. The real verbs are: **monitor, operate, communicate,
diagnose, repair, document, delegate.**

## The nested core loops

### Minute loop — Operate
Watch instruments, manage the power/thermal envelope, respond to annunciators, work the
radio. Tension source: the ship is always slightly out of equilibrium; sensors are the only
truth you have, and they are not always truthful.

### Hour loop — The Leg
A mission leg: plan (power budget, MEL review, flight plan filing) → depart (clearances,
checklists) → transit (time compression, scheduled maintenance, drifting parameters) →
arrive (approach phraseology, docking). Tension source: commitments made under uncertainty.

### Session loop — The Casualty
Something breaks. The signature experience, expected to dominate memorable sessions:

1. **Symptom** — an annunciator, a drifting gauge, a bus analyzer anomaly, a smell
   (reported by crew).
2. **Stabilize** — QRH abnormal checklist. Buy time; shed load; isolate.
3. **Diagnose** — FIM decision tree. Pull telemetry, probe test points, swap suspects.
4. **Repair** — LRU/SRU swap, board-level repair (low TL), jury-rig (logged as
   nonconformance), or accept degraded ops per MEL.
5. **Verify & document** — functional test procedure; write-up in the ship log/notebook.
   The FDR review screen lets you reconstruct what actually happened.

### Campaign loop — The Ship of Theseus
Earn contracts → acquire parts/manuals/crew → integrate higher-TL equipment (power vs.
knowability trade) → your ship becomes a unique patchwork with a unique failure
personality. Knowledge compounds: your notebook and your crew's experience are the save
game's real wealth. See [scenarios-and-campaign.md](scenarios-and-campaign.md).

## What the player actually does, concretely

| Verb | Example |
|---|---|
| Operate | `eps bus.a.tie close` after confirming source voltage per SOM 24-30-01. |
| Monitor | Watch BUS A amps creep as a coolant pump bearing degrades. |
| Communicate | "Meridian Approach, UEV Kestrel, information BRAVO, request docking bay four." |
| Diagnose | FIM 24-41 TASK 3: measure TP-104 to TP-GND, expect 12.0 ± 0.3 V. |
| Repair | Swap SRU board A2 in PDU-2; run functional test FT-24-41-A. |
| Delegate | Order engineer NPC: "Ramos, run QRH E-3 on the aft loop, report when complete." |
| Document | Notebook entry: "Bay 4 umbilical pin 7 intermittent — wiggle test positive." |

## Difficulty model

Difficulty is **documentation and consequence**, never simulation dishonesty.

| Setting axis | Easy end | Hard end |
|---|---|---|
| Docs completeness | Full SOM/FIM/WDM + tooltips citing manual sections | Manuals only, some pages missing/wrong revision |
| Assistance | Crew suggests FIM entry points | Crew executes only literal orders |
| Consequence | Failures pause the sim politely | Real-time cascade, permadeath ships |
| World | Forgiving controllers, generous MEL | Violations recorded, audits, insurance |

The simulation itself always runs at full fidelity. An "easy" game is a well-documented
ship with a good crew, which is exactly how it works in real aerospace.

## Session shape & pacing guardrails

- Target session: 45–120 min (one leg, or one casualty worked end to end).
- Time compression up to 1000×, auto-dropping to 1× on defined event classes
  (annunciator, radio call addressed to you, threshold crossings).
- The game must always be pausable; all commands queueable while paused (orders execute
  on resume). Real-time pressure is a difficulty setting, not a foundation.

## What ships in the box (fantasy of the physical product)

Even digitally, the game presents as: the ship, the crew, and **the binder** — SOM, QRH,
FIM, WDM, IPC, MEL, CPM, exportable to HTML/PDF for printing. The binder is a first-class
deliverable; see [manuals-as-gameplay.md](manuals-as-gameplay.md).

## Open questions

- OQ-GO-1: Persistent single ship vs. fleet later? (Lean: single ship through 1.0.)
- OQ-GO-2: Permadeath default? (Lean: ship loss is career event, not save wipe.)
- OQ-GO-3: How much piloting/astrodynamics in v1? (Lean: burns as planned events with
  execution monitoring; no manual joystick flight.)
