<!-- GENERATED FILE — DO NOT EDIT (ultraspace generate). -->
<!-- Source: ships/tb-1/blueprint.yaml + the part catalog. -->
<!-- Style: data/manuals/style-guide.md. Hand edits fail CI. -->


# WDM 42 — Generated Data Sheets — TB-1 Breadboard (core:tb-1)

## Data bus DB-A {#bus-db.a}

Termination: 78 ohm at both ends (BC end and far end).
Stubs: transformer-coupled — a stub fault is contained to its terminal.

```
Trunk order (from the BC): bc.a — seg.bc-j1 — j1 — seg.j1-j2 — j2 — (end)
Stub taps: j1 → stub.j1-rt5 → RT 5 (rt.5); j2 → stub.j2-rt12 → RT 12 (rt.12)
DMM probe points (de-energized bus only): j1, j2
```
