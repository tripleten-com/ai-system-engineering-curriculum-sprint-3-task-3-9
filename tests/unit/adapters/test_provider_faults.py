"""Coldline.

===================

File:              tests/unit/adapters/test_provider_faults.py
Component:         Unit tests — Provider emulator fault controls
Purpose:           Unit tests for the fault flag, the stall, and the provider that honours them.
Interacts With:    One isolated source responsibility
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Fast feedback, failure paths, fault injection
Tools:             Python 3.12, pytest
"""

import time
from pathlib import Path

import pytest

from adapters.model import DeterministicModelProvider, ProviderFaultControls
from adapters.model import faults as fault_module
from domain.contracts import ModelRequest
from domain.errors import TerminalProviderError

REQUEST = ModelRequest(
    exception_id="exc-fault-001",
    shipment_id="shipment-syn-001",
    temperature_c=9.2,
    allowed_min_c=2.0,
    allowed_max_c=8.0,
)


def test_controls_apply_read_and_lift_one_fault(tmp_path: Path) -> None:
    """The flag file carries exactly the applied fault and nothing once lifted."""
    controls = ProviderFaultControls(tmp_path / "fault")

    assert controls.current() is None
    controls.apply("stall")
    assert controls.current() == "stall"
    controls.lift()
    assert controls.current() is None
    controls.lift()  # lifting twice is not an error


def test_controls_reject_an_unknown_fault(tmp_path: Path) -> None:
    """Only the supplied fault can be applied; a typo never silently arms nothing."""
    controls = ProviderFaultControls(tmp_path / "fault")

    with pytest.raises(ValueError, match="unknown provider fault"):
        controls.apply("outage")
    assert controls.current() is None


def test_an_unrecognised_flag_is_treated_as_no_fault(tmp_path: Path) -> None:
    """A flag file with unexpected content leaves the emulator behaving normally."""
    path = tmp_path / "fault"
    path.write_text("something-else\n", encoding="utf-8")

    assert ProviderFaultControls(path).current() is None


@pytest.mark.asyncio
async def test_provider_stalls_and_fails_terminally_while_the_fault_is_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `stall` applied every call blocks for the stall duration, then fails terminally."""
    monkeypatch.setattr(fault_module, "STALL_SECONDS", 0.05)
    controls = ProviderFaultControls(tmp_path / "fault")
    provider = DeterministicModelProvider(latency_ms=0, faults=controls)
    controls.apply("stall")

    started = time.perf_counter()
    with pytest.raises(TerminalProviderError, match="stall"):
        await provider.summarize(REQUEST)
    assert time.perf_counter() - started >= 0.05

    controls.lift()
    response = await provider.summarize(REQUEST)
    assert response.provider == "deterministic-local"


@pytest.mark.asyncio
async def test_provider_without_controls_ignores_any_flag(tmp_path: Path) -> None:
    """A provider composed without fault controls never reads a flag file."""
    path = tmp_path / "fault"
    ProviderFaultControls(path).apply("stall")

    response = await DeterministicModelProvider(latency_ms=0).summarize(REQUEST)

    assert "operational review is required" in response.summary


def test_command_line_applies_reports_and_lifts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The container command reports the state a run reads back."""
    path = str(tmp_path / "fault")

    assert fault_module.main(["--path", path, "status"]) == 0
    assert capsys.readouterr().out.strip() == "none"
    assert fault_module.main(["--path", path, "apply", "stall"]) == 0
    assert capsys.readouterr().out.strip() == "applied stall"
    assert fault_module.main(["--path", path, "status"]) == 0
    assert capsys.readouterr().out.strip() == "stall"
    assert fault_module.main(["--path", path, "lift"]) == 0
    assert capsys.readouterr().out.strip() == "lifted"
    assert fault_module.main(["--path", path, "status"]) == 0
    assert capsys.readouterr().out.strip() == "none"
