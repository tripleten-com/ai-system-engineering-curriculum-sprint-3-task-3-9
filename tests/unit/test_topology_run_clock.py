"""Coldline.

===================

File:              tests/unit/test_topology_run_clock.py
Component:         Unit tests — Topology run clock
Purpose:           Keep the topology run's clock anchored at the load step's first request.
Interacts With:    infra/topology/topology_run.py
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Controlled load experiments, one independent variable, comparable runs
Tools:             Python 3.12, pytest
"""

import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

TASK_ROOT = Path(__file__).resolve().parents[2]


def _load_runner() -> ModuleType:
    """Load the runner script as a module, the way `poe topology-run` runs it."""
    spec = importlib.util.spec_from_file_location(
        "topology_run", TASK_ROOT / "infra/topology/topology_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


class _FakeLoadStep:
    """Stand in for the load step process: running until told it exited."""

    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode

    def poll(self) -> int | None:
        return self.returncode


def _record(start_time: float, exception_id: str) -> dict[str, Any]:
    """Build one accepted-submission record as the load step prints it."""
    return {
        "kind": "request",
        "start_time": start_time,
        "response_time_ms": 12.0,
        "status": 202,
        "ok": True,
        "exception_id": exception_id,
    }


def test_the_first_record_sets_the_clock_once() -> None:
    """Only the first request starts the clock; later records leave it where it is."""
    log = runner.RunLog()
    runner._record_submission(log, _record(100.0, "exc-1"))
    runner._record_submission(log, _record(101.5, "exc-2"))

    assert log.first_request_at == 100.0
    assert log.first_request.is_set()


def test_the_clock_starts_at_the_first_request_not_at_the_launch() -> None:
    """A slow Locust start moves the clock with it, so the window keeps its place in the load."""
    launched_at = time.time() - 11.0
    log = runner.RunLog()
    runner._record_submission(log, _record(launched_at + 11.0, "exc-1"))

    started_at = runner._wait_for_first_request(_FakeLoadStep(), log, launched_at)

    assert started_at == launched_at + 11.0


def test_a_load_step_that_exits_before_its_first_request_is_reported() -> None:
    """Name the load step's own error instead of waiting out the start timeout."""
    log = runner.RunLog()
    log.load_step_errors.append("ConnectionRefusedError")

    with pytest.raises(runner.TopologyRunError, match="stopped before its first request"):
        runner._wait_for_first_request(_FakeLoadStep(returncode=1), log, time.time())


def test_a_load_step_that_never_sends_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A load step that stays silent fails the run instead of hanging it."""
    monkeypatch.setattr(runner, "LOAD_STEP_START_TIMEOUT_SECONDS", 0.0)

    with pytest.raises(runner.TopologyRunError, match="sent no request"):
        runner._wait_for_first_request(_FakeLoadStep(), runner.RunLog(), time.time())


def test_the_run_zero_moves_to_an_earlier_request_that_answered_later() -> None:
    """A request that started first but answered second sets the zero, so no offset is negative."""
    log = runner.RunLog()
    runner._record_submission(log, _record(100.02, "exc-1"))
    runner._record_submission(log, _record(100.0, "exc-2"))

    assert log.first_request_at == 100.02
    assert runner._earliest_request_start(log, 100.02) == 100.0
