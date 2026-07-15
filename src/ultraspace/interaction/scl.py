"""SCL v1: parse and dispatch (docs/design/command-language.md).

Grammar (M1 subset — no numeric args yet, so the units rule is dormant):

    command := address-words verb [--flag ...]

Address words are joined with '.' and matched longest-prefix against the
ship's address map, so ``eps bus.a.tie open`` and ``eps.bus.a.tie open`` are
identical. Every accepted or refused command lands in the FDR journal — the
journal is the replay input (ADR-0002).
"""

from __future__ import annotations

from ultraspace.ship import CommandResult, Simulation
from ultraspace.ship.devices import refused

__all__ = ["Dispatcher"]


class Dispatcher:
    def __init__(self, sim: Simulation) -> None:
        self.sim = sim
        self._roots = sorted({address.split(".")[0] for address in sim.address_map})

    def execute_line(self, line: str) -> CommandResult:
        result = self._execute(line)
        self.sim.log.append(
            self.sim.clock.tick_index,
            "scl",
            "command",
            {"line": line.strip(), "ok": result.ok},
        )
        return result

    def _execute(self, line: str) -> CommandResult:
        tokens = line.split()
        flags = {t.removeprefix("--") for t in tokens if t.startswith("--")}
        words = [t for t in tokens if not t.startswith("--")]
        if not words:
            return refused("empty command")

        # Longest prefix of words (dot-joined) that names a known address.
        for k in range(len(words), 0, -1):
            address = ".".join(words[:k])
            if address in self.sim.address_map:
                if k == len(words):
                    return refused(f"{address}: missing verb")
                verb = words[k]
                return self.sim.execute(address, verb, flags)
            if address in self._roots:
                # System-level address: only summary read is defined at M1.
                if k < len(words) and words[k] == "read":
                    return CommandResult(True, self.sim.summary())
                return refused(f"{address}: only 'read' is supported at system level")
        return refused(f"unknown address {words[0]!r} (try '<system> read' for a summary)")
