"""Coldline.

===================

File:              src/adapters/model/faults.py
Component:         Adapter — Provider emulator fault controls
Purpose:           Apply, lift, and read the one supplied failure the provider emulator offers.
Interacts With:    adapters.model.deterministic, the Task 3.9 topology run, docker compose exec
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Fault injection, blast radius, deterministic emulation
Tools:             Python 3.12

The emulator is an in-process adapter, so a fault has to reach it from outside the
container without a network endpoint. The control is one flag file inside the container's
own filesystem: ``apply`` writes the fault's name into it, ``lift`` removes it, and the
provider reads it at the start of every ``summarize`` call. The file lives under ``/tmp``,
which the unprivileged runtime user can write, and it is per container, so applying a
fault to the worker never touches another container's emulator.

Commands, run inside the container that hosts the worker loop:

    python -m adapters.model.faults apply stall   # every provider call now stalls, then fails
    python -m adapters.model.faults lift          # back to the deterministic summary
    python -m adapters.model.faults status        # print the active fault, or `none`

One fault is supplied. ``stall`` makes the emulated provider behave like a synchronous
provider client whose call hangs: it blocks the calling thread for ``STALL_SECONDS`` and
then raises a terminal provider failure, so the reading it was summarizing ends ``FAILED``.
Because the block is synchronous it holds whatever thread, and therefore whatever event
loop, the worker loop runs on. In the split profile that is the worker container's own
loop and nothing else; in the single-process profile it is the one loop the API routes
share with the worker loop. That difference is the blast radius Task 3.9 measures.
"""

import argparse
import sys
import time
from pathlib import Path

from domain.errors import TerminalProviderError

FAULT_PATH = Path("/tmp/coldline-provider-fault")
STALL = "stall"
FAULTS = (STALL,)
# How long one stalled provider call blocks its thread before it fails. Longer than the
# resilient wrapper's per-attempt timeout on purpose: a synchronous hang cannot be
# interrupted by an asyncio timeout, which is exactly what the single-process profile
# exposes. Read at call time so a test can shorten it.
STALL_SECONDS = 2.5


class ProviderFaultControls:
    """Read and change the one fault flag the deterministic provider consults."""

    def __init__(self, path: Path = FAULT_PATH) -> None:
        """Bind the controls to one flag file; the default is the container's own."""
        self._path = path

    @property
    def path(self) -> Path:
        """Return the flag file these controls read and write."""
        return self._path

    def current(self) -> str | None:
        """Return the active fault's name, or None when the emulator behaves normally."""
        try:
            name = self._path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except OSError:
            return None
        return name if name in FAULTS else None

    def apply(self, fault: str) -> None:
        """Activate one supplied fault for every provider call that starts from now on."""
        if fault not in FAULTS:
            raise ValueError(f"unknown provider fault {fault!r}; supplied: {', '.join(FAULTS)}")
        self._path.write_text(fault + "\n", encoding="utf-8")

    def lift(self) -> None:
        """Deactivate whatever fault is applied; a call already stalling still finishes."""
        self._path.unlink(missing_ok=True)


def stall(seconds: float | None = None) -> None:
    """Block the calling thread, as a hanging synchronous provider client does, then fail."""
    duration = STALL_SECONDS if seconds is None else seconds
    time.sleep(duration)
    raise TerminalProviderError(
        f"provider emulator fault: {STALL} held the call for {duration:.1f} s and then failed"
    )


def main(argv: list[str] | None = None) -> int:
    """Apply, lift, or print the emulator fault from the command line."""
    parser = argparse.ArgumentParser(description="Control the deterministic provider's fault.")
    parser.add_argument("--path", type=Path, default=FAULT_PATH, help="the flag file to use")
    commands = parser.add_subparsers(dest="command", required=True)
    apply_parser = commands.add_parser("apply", help="activate one supplied fault")
    apply_parser.add_argument("fault", choices=FAULTS)
    commands.add_parser("lift", help="deactivate the fault")
    commands.add_parser("status", help="print the active fault, or none")
    args = parser.parse_args(argv)
    controls = ProviderFaultControls(args.path)
    if args.command == "apply":
        controls.apply(args.fault)
        print(f"applied {args.fault}")
    elif args.command == "lift":
        controls.lift()
        print("lifted")
    else:
        print(controls.current() or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
