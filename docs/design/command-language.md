# SCL — Ship Command Language

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design+engineering
Related: [ui-presentation.md](ui-presentation.md),
[../engineering/architecture.md](../engineering/architecture.md)

SCL is the single interaction layer between any human (or test harness, or crew AI) and
the ship. **Every** panel click, hotkey, and crew action emits SCL; the FDR records SCL;
replays re-execute it. One interaction layer means one thing to test, one thing to
document, one thing to replay.

## Design goals

1. Speakable like real ops jargon ("open the bus tie" → `eps bus.a.tie open`).
2. Discoverable without being guessable-to-victory: completion shows *syntax*, the
   manual supplies *values and order* (the manual bar lives in parameters/procedures,
   not in obscure spelling).
3. Deterministic, serializable, versioned — it is an API with a fictional accent.

## Grammar (v1)

```
command   := address verb [args] [flags]
address   := path | alias
path      := segment ('.' segment)*        e.g. eps.bus.a.tie, pdu2.a2.tp104
verb      := system-defined                e.g. open, close, read, set, arm, execute
args      := literals with units           e.g. 28v, 3.2a, 45%, 120s, on, off
flags     := '--'key[=value]               e.g. --confirm, --log="pre-burn check"
```

- **Addresses** come from the ship blueprint (data-driven); tab completion is generated
  from the loaded ship, so completion is *per your actual hardware* — an unlabeled TL3
  artifact completes as `unk.artifact-c` until you name it in the notebook.
- **Aliases**: player-defined and manual-defined shorthands (`be` → `eps.bus.e`). SOM
  procedures always use full paths (manuals are unambiguous).
- **Units are mandatory** on dimensioned args; bare numbers are rejected with the
  expected unit in the error. No unit guessing, ever (Mars Climate Orbiter rule).

## Safety semantics (the interlock model)

| Class | Syntax behavior |
|---|---|
| Routine | Immediate: `eps bus.a.load 12 shed` |
| Guarded | Requires `--confirm`: energizing buses, opening pressurized valves |
| **Armed** | Two-command: `prop main arm` … `prop main execute` (arm times out in 30 s). Irreversibles: pyro valves, fuel dump, ejecting an SRU into space |
| Interlocked | Refused while interlock condition holds, with the interlock named: `REFUSED: interlock DOCK-CLAMPS-ENGAGED (see SOM 32-20-02)`. Jumpering an interlock is a repair-verb-level act that lands in the nonconformance log |

Error messages always name the manual section that explains the refusal — errors teach.

## Reading state (instrument-mediated, always)

`read` verbs return *instrument* values with provenance and staleness:

```
> eps bus.a read
BUS A   27.6 V   41.2 A    src: XDCR MT-24-104 via DB-A   age 0.2 s
> pdu2.a2.tp104 read --probe dmm1
TP-104  11.94 V  (DMM-1, range 20V)        ← requires physical probe placement state
```

If the transducer is dead you get `--- NO DATA (MT-24-104 no report, 42 s)`, not the
truth. No God View is enforced at the SCL layer: there is no debug verb in the shipping
grammar that bypasses instrumentation (dev builds have a separate, visually loud
`godmode.*` namespace, stripped from release).

## Scripts and checklists

- SCL scripts = executable checklists. SOM/QRH procedures compile to annotated scripts
  (steps + expected indications + holds). Running one steps interactively:
  execute → verify indication → advance/hold/branch.
- Crew execute procedures through the same runner (their skill modulates step timing and
  error injection). The CI procedure runner is this exact machinery, headless — the
  manual-conformance test *is* the crew execution path (one implementation, three users:
  player, crew AI, CI).

## Journal & replay

Every accepted command → FDR with tick, issuer (player/crew/system), source (typed,
panel, script step), and outcome. `journal` verbs let the player grep their own history
("what did I actually do before the trip?") — self-FDR-review as gameplay and as bug
reporting (attach journal segment to reports).

## Example session (M1 target, EPS cold start fragment)

```
> eps read --summary
EPS: COLD. Batteries: BAT-1 76% 25.1V, BAT-2 74% 25.0V. All buses de-energized.
> eps bat.1.contactor close --confirm
BAT-1 contactor closed. ESSENTIAL BUS E: 25.1 V.        [SOM 24-30-01 step 4]
> eps bus.a.precharge start
REFUSED: interlock BUS-A-TIE-OPEN not satisfied (tie is closed). See SOM 24-30-01 note 2.
> eps bus.a.tie open
BUS A tie: OPEN.
> eps bus.a.precharge start
Precharge in progress... BUS A 3 V ... 12 V ... 24.8 V. Complete (4.1 s).
> eps bus.a.tie close --confirm
BUS A tie: CLOSED. BUS A: 25.0 V, 2.1 A.
```

(The precharge-before-tie ordering is a canonical "manual bar" constraint: closing the
tie onto a discharged bus slams inrush through the tie contactor — the SOM explains why,
and doing it anyway wears/welds the contactor. Honest physics, taught by the manual.)

## Versioning

Grammar versions with the save format. Verbs/addresses may be added freely; renames
require deprecation aliases for one minor version (replays must keep executing).

## Open questions

- OQ-SCL-1: Localization strategy — SCL stays English-as-jargon (like real aviation) with
  localized help? (Lean: yes.)
- OQ-SCL-2: Vim-like modal input at stations vs. single global prompt? (Prototype at M2.)
