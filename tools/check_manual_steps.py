#!/usr/bin/env python3
"""Printed step numbers must match the procedure they claim to be (ADR-0005).

A manual page and its procedure are two artifacts that can drift: a step
inserted in the YAML and not in the prose ships a checklist that lies about
its own numbering. This gate closes exactly that gap and nothing wider.

Only fenced blocks that immediately follow a line of the form

    Execute per checklist `<procedure-id>`:

are checked. FIM trees print section-local numbering in their *worked* blocks
(FIM 42-12 §2 and §3 both start at 1); those carry no claim line and are not
this gate's business.

The rule a claimed block must satisfy: **the card prints the walk, and the
verdict steps are prose.** Printed numbers must be exactly 1..K of the
procedure's own numbering, and every step past K must be a verdict step
(``on_pass_goto: 0`` — a branch target that ends the checklist). That is what
the manuals already do, and it fails the drift that actually happens: a step
inserted in the YAML shifts a live step into the unprinted tail, where it does
not belong. See engineering/testing.md.

Run: uv run python tools/check_manual_steps.py   (wired into `make lint`)
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANUALS = ROOT / "data" / "manuals"
PROCEDURES = ROOT / "data" / "procedures"

#: The line that binds a printed block to an executable procedure.
CLAIM = re.compile(r"^Execute per checklist `([a-z0-9-]+)`:\s*$")
#: A printed step: its number sits in a right-aligned two-wide field.
PRINTED_STEP = re.compile(r"^ {0,2}(\d+)\. ")


def procedure_steps() -> dict[str, list[dict[str, object]]]:
    steps: dict[str, list[dict[str, object]]] = {}
    for path in sorted(PROCEDURES.rglob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict) or spec.get("schema") != "procedure/1":
            continue
        steps[spec["id"]] = spec["steps"]
    return steps


def verdict(step: dict[str, object]) -> bool:
    """A step whose only exit is ending the checklist — printed as prose."""
    return step.get("on_pass_goto") == 0


def printed_blocks(text: str) -> list[tuple[int, str, list[int]]]:
    """(line number, procedure id, printed step numbers) per claimed block."""
    lines = text.splitlines()
    blocks: list[tuple[int, str, list[int]]] = []
    for index, line in enumerate(lines):
        claim = CLAIM.match(line)
        if claim is None:
            continue
        fence = index + 1
        while fence < len(lines) and not lines[fence].strip():
            fence += 1
        if fence >= len(lines) or not lines[fence].startswith("```"):
            blocks.append((index + 1, claim.group(1), []))
            continue
        numbers: list[int] = []
        for body in lines[fence + 1 :]:
            if body.startswith("```"):
                break
            step = PRINTED_STEP.match(body)
            if step is not None:
                numbers.append(int(step.group(1)))
        blocks.append((index + 1, claim.group(1), numbers))
    return blocks


def main() -> int:
    steps = procedure_steps()
    errors: list[str] = []
    for path in sorted(MANUALS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(ROOT)
        for lineno, proc_id, printed in printed_blocks(text):
            if proc_id not in steps:
                errors.append(f"{where}:{lineno}: no procedure {proc_id!r}")
                continue
            walk = steps[proc_id]
            if printed != list(range(1, len(printed) + 1)) or len(printed) > len(walk):
                errors.append(
                    f"{where}:{lineno}: printed steps {printed} are not "
                    f"{proc_id} steps 1..{len(printed)}"
                )
                continue
            unprinted = [s["step"] for s in walk[len(printed) :] if not verdict(s)]
            if unprinted:
                errors.append(
                    f"{where}:{lineno}: {proc_id} steps {unprinted} are not printed "
                    f"and are not verdict steps"
                )
    for error in errors:
        print(f"MANUAL-STEPS {error}")
    print(f"check_manual_steps: {'FAILED' if errors else 'ok'} ({len(errors)} error(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
