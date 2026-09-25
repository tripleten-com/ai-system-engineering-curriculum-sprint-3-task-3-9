"""Coldline.

===================

File:              infra/topology/topology_run.py
Component:         Topology tools — Experiment runner
Purpose:           Run the pinned load step and one provider failure against the running profile.
Interacts With:    Both Compose files, loadtest/locustfile.py, the fault control, the API, Jaeger
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Topology experiment, latency percentiles, throughput, blast radius, evidence
Tools:             Python 3.12, Docker Compose, Locust, httpx, Jaeger

``poe topology-run`` is the whole experiment, and it takes no options: the same command
runs against whichever profile is up, so the two runs a student compares differ in the
topology alone. In order, it

1. detects the running profile from ``docker compose ps`` (``api`` and ``worker`` running
   means ``split``; ``single`` running means ``single``) and lifts any provider fault a
   previous, interrupted run may have left behind;
2. starts the pinned load step (``infra/topology/load_step.py``, the ``ColdlineUser`` from
   ``loadtest/locustfile.py`` with ``poe load-test``'s users, spawn rate and 30 s) and, as
   each accepted reading arrives, polls its status every half second until it reaches a
   terminal state;
3. ten seconds in, applies the supplied provider failure (``stall``) through the emulator's
   fault control inside the container that runs the worker loop, and lifts it again ten
   seconds later, so the failure window sits inside the run;
4. after the load step ends, waits for every accepted reading to settle;
5. looks up one Jaeger trace for a few of the readings, some whose summary attempt met the
   failure window and some outside it;
6. writes ``docs/student/topology/<profile>-run.json`` with a generator marker and a
   content digest that ``poe topology-contract`` verifies.

Definitions used in the summary, so the two runs are read the same way:

- ``readings_p95_ms``/``readings_p50_ms``: latency of the successful ``POST /api/v1/readings``
  requests the load step sent, over the whole run.
- ``status_p95_ms``/``status_p50_ms``: latency of the successful
  ``GET /api/v1/exceptions/{exception_id}`` reads this runner made; a read that timed out
  is counted as a failed status read, not as a latency.
- ``throughput_per_second``: readings that reached a terminal state, divided by the seconds
  from the first request to the moment the last reading settled.
- The failure window opens when the fault control confirms the fault is applied and closes
  when it confirms the fault is lifted. A reading is "inside" it when it reached its terminal
  state while the window was open, or ended ``FAILED`` because of the fault; a request is
  inside it when it started while the window was open. ``failure_window_errors`` is the
  count of inside-window submissions that failed, inside-window status reads that failed,
  and inside-window readings that ended ``FAILED``.

Never edit a summary. Rerun instead; the new summary replaces the old one.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

TASK_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_DIR = TASK_ROOT / "docs/student/topology"
LOAD_STEP = TASK_ROOT / "infra/topology/load_step.py"
COMPOSE_PROFILES = ("--profile", "observability", "--profile", "localstack")
SINGLE_FILES = ("-f", "compose.yaml", "-f", "compose.single.yaml")
GENERATOR = "poe topology-run"
SUMMARY_SCHEMA = "coldline-topology-run/1"
PROFILES = ("split", "single")
# The first-party Compose services each profile runs, and the one that hosts the worker
# loop (where the emulator, and so its fault control, lives).
PROFILE_SERVICES = {"split": ("api", "worker"), "single": ("single",)}
FAULT_HOST_SERVICE = {"split": "worker", "single": "single"}
# The telemetry identity each profile's spans carry; the trace lookup asks Jaeger by it.
TRACE_SERVICE = {"split": "coldline-api", "single": "coldline-single"}
# The pinned load step, exactly `poe load-test`'s shape.
LOAD_USERS = 2
LOAD_SPAWN_RATE = 2.0
LOAD_SECONDS = 30.0
FAULT = "stall"
FAULT_APPLY_AT_SECONDS = 10.0
FAULT_LIFT_AT_SECONDS = 20.0
STATUS_POLL_INTERVAL_SECONDS = 0.5
STATUS_READ_TIMEOUT_SECONDS = 1.0
SETTLE_TIMEOUT_SECONDS = 120.0
LOAD_STEP_GRACE_SECONDS = 30.0
TERMINAL_STATES = frozenset({"COMPLETED", "FAILED"})
FAULT_FAILURE_REASON = "model_provider_terminal_failure"
SAMPLES_PER_SIDE = 3
TRACE_WAIT_SECONDS = 30.0


class TopologyRunError(RuntimeError):
    """Report one actionable failure of the experiment without a stack trace."""


@dataclass
class Reading:
    """One reading the load step submitted, and what its status reads showed."""

    exception_id: str
    accepted_at: float
    state: str | None = None
    failure_reason: str | None = None
    terminal_at: float | None = None


@dataclass
class RunLog:
    """Everything the run observed, shared between the reader, the poller and the main thread."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    submissions: list[dict[str, Any]] = field(default_factory=list)
    status_reads: list[dict[str, Any]] = field(default_factory=list)
    readings: dict[str, Reading] = field(default_factory=dict)
    load_step_errors: list[str] = field(default_factory=list)

    def pending(self) -> list[Reading]:
        """Return the readings that have not reached a terminal state yet."""
        with self.lock:
            return [reading for reading in self.readings.values() if reading.state is None]


# --- host configuration -------------------------------------------------------------------


def _host_port(name: str, default: int) -> int:
    """Return one host port from the shell, the local `.env`, or the documented default."""
    value = os.environ.get(name)
    dotenv = TASK_ROOT / ".env"
    if value is None and dotenv.is_file():
        for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith(f"{name}="):
                value = line.split("=", maxsplit=1)[1].strip().strip('"').strip("'")
    if value is None:
        return default
    try:
        port = int(value)
    except ValueError as exc:
        raise TopologyRunError(f"{name} must be an integer host port") from exc
    if not 1 <= port <= 65_535:
        raise TopologyRunError(f"{name} must be between 1 and 65535")
    return port


# --- the running profile -----------------------------------------------------------------


def compose_command(profile: str | None, *arguments: str) -> list[str]:
    """Return one Docker Compose command line for the given profile's configuration."""
    files = SINGLE_FILES if profile == "single" else ()
    return ["docker", "compose", *files, *COMPOSE_PROFILES, *arguments]


def compose_records() -> list[dict[str, Any]]:
    """Return every Compose container record for this project, orphans included."""
    result = subprocess.run(
        compose_command(None, "ps", "--all", "--format", "json"),
        cwd=TASK_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise TopologyRunError(f"docker compose ps failed: {result.stderr.strip()}")
    text = result.stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        loaded = json.loads(text)
        return [entry for entry in loaded if isinstance(entry, dict)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def running_services(records: list[dict[str, Any]]) -> set[str]:
    """Return the names of the first-party services whose container is running."""
    return {
        str(record.get("Service"))
        for record in records
        if record.get("State") == "running" and record.get("Service") in {"api", "worker", "single"}
    }


def detect_profile() -> str:
    """Name the running profile, or explain why neither is running cleanly."""
    running = running_services(compose_records())
    if running == {"api", "worker"}:
        return "split"
    if running == {"single"}:
        return "single"
    if not running:
        raise TopologyRunError(
            "no profile is running: start one with `poe start` (split) or "
            "`poe start-single` (single-process), then `poe ready`"
        )
    raise TopologyRunError(
        f"the running containers ({', '.join(sorted(running))}) are neither the split "
        "profile (api and worker) nor the single-process profile (single); restart one "
        "profile with `poe start` or `poe start-single`"
    )


def fault_control(profile: str, *arguments: str) -> str:
    """Run the emulator's fault control inside the container that hosts the worker loop."""
    service = FAULT_HOST_SERVICE[profile]
    result = subprocess.run(
        compose_command(
            profile, "exec", "-T", service, "python", "-m", "adapters.model.faults", *arguments
        ),
        cwd=TASK_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no detail"
        raise TopologyRunError(
            f"the fault control failed in the {service} container ({' '.join(arguments)}): {detail}"
        )
    return result.stdout.strip()


def require_ready(base_url: str) -> None:
    """Refuse to measure a stack that is not ready; warm-up would end up in the percentiles."""
    try:
        response = httpx.get(f"{base_url}/health/ready", timeout=5.0)
    except httpx.HTTPError as exc:
        raise TopologyRunError(f"the API at {base_url} did not answer: {exc}") from exc
    if response.status_code != 200:
        raise TopologyRunError(
            f"the API at {base_url} answered {response.status_code} on /health/ready; "
            "run `poe ready` and wait for it to pass before `poe topology-run`"
        )


# --- the load step and the status poller ---------------------------------------------------


def start_load_step(base_url: str, log: RunLog) -> tuple[subprocess.Popen[str], threading.Thread]:
    """Start the pinned load step as its own process and read its request records."""
    process = subprocess.Popen(
        [
            sys.executable,
            str(LOAD_STEP),
            "--host",
            base_url,
            "--users",
            str(LOAD_USERS),
            "--spawn-rate",
            str(LOAD_SPAWN_RATE),
            "--run-time",
            str(LOAD_SECONDS),
        ],
        cwd=TASK_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )

    def read_stdout() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict) or record.get("kind") != "request":
                continue
            _record_submission(log, record)

    def read_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            if line.strip():
                log.load_step_errors.append(line.rstrip())

    reader = threading.Thread(target=read_stdout, name="load-step-stdout", daemon=True)
    reader.start()
    threading.Thread(target=read_stderr, name="load-step-stderr", daemon=True).start()
    return process, reader


def _record_submission(log: RunLog, record: dict[str, Any]) -> None:
    """Keep one load-step request record, and start following the reading it accepted."""
    start_time = record.get("start_time")
    started = float(start_time) if isinstance(start_time, int | float) else time.time()
    response_ms = record.get("response_time_ms")
    ok = bool(record.get("ok")) and record.get("status") == 202
    exception_id = record.get("exception_id")
    with log.lock:
        log.submissions.append(
            {
                "started_at": started,
                "response_ms": float(response_ms) if isinstance(response_ms, int | float) else None,
                "ok": ok,
                "status": record.get("status"),
            }
        )
        if ok and isinstance(exception_id, str) and exception_id not in log.readings:
            log.readings[exception_id] = Reading(exception_id=exception_id, accepted_at=started)


def poll_statuses(base_url: str, log: RunLog, stop: threading.Event) -> None:
    """Poll every pending reading's status until it is terminal or the run stops."""
    with httpx.Client(base_url=base_url, timeout=STATUS_READ_TIMEOUT_SECONDS) as client:
        while not stop.is_set():
            for reading in log.pending():
                if stop.is_set():
                    break
                started = time.time()
                try:
                    response = client.get(f"/api/v1/exceptions/{reading.exception_id}")
                    response.raise_for_status()
                    body = response.json()
                except (httpx.HTTPError, ValueError):
                    with log.lock:
                        log.status_reads.append({"at": started, "response_ms": None, "ok": False})
                    continue
                elapsed_ms = (time.time() - started) * 1000
                with log.lock:
                    log.status_reads.append(
                        {"at": started, "response_ms": round(elapsed_ms, 3), "ok": True}
                    )
                    state = body.get("state") if isinstance(body, dict) else None
                    if isinstance(state, str) and state in TERMINAL_STATES:
                        reading.state = state
                        reason = body.get("failure_reason")
                        reading.failure_reason = reason if isinstance(reason, str) else None
                        reading.terminal_at = time.time()
            stop.wait(STATUS_POLL_INTERVAL_SECONDS)


# --- the figures -----------------------------------------------------------------------------


def percentile(values: list[float], fraction: float) -> float | None:
    """Return the nearest-rank percentile of the values, rounded to a tenth of a millisecond."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return round(ordered[rank - 1], 1)


def in_window(moment: float | None, window: tuple[float, float]) -> bool:
    """Return whether one instant falls inside the failure window, inclusive."""
    return moment is not None and window[0] <= moment <= window[1]


def reading_inside_window(reading: Reading, window: tuple[float, float]) -> bool:
    """Return whether one reading's summary attempt met the failure window."""
    if reading.failure_reason == FAULT_FAILURE_REASON:
        return True
    return in_window(reading.terminal_at, window)


def digest(summary: dict[str, Any]) -> str:
    """Return the content digest of a summary, over everything but the digest itself.

    ``tests/contract/topology_contract.py`` recomputes this from the file exactly the
    same way; the two must stay identical.
    """
    body = {key: value for key, value in summary.items() if key != "digest"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_summary(
    *,
    profile: str,
    services: list[str],
    started_at: float,
    settled_at: float,
    window: tuple[float, float],
    log: RunLog,
    sampled: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the summary from the run log; the digest is added last."""
    with log.lock:
        submissions = list(log.submissions)
        status_reads = list(log.status_reads)
        readings = list(log.readings.values())
    successful_submissions = [
        entry["response_ms"] for entry in submissions if entry["ok"] and entry["response_ms"]
    ]
    successful_reads = [
        entry["response_ms"] for entry in status_reads if entry["ok"] and entry["response_ms"]
    ]
    terminal = [reading for reading in readings if reading.state in TERMINAL_STATES]
    failed = [reading for reading in readings if reading.state == "FAILED"]
    run_seconds = max(settled_at - started_at, 0.001)
    window_submissions_failed = sum(
        1 for entry in submissions if not entry["ok"] and in_window(entry["started_at"], window)
    )
    window_reads_failed = sum(
        1 for entry in status_reads if not entry["ok"] and in_window(entry["at"], window)
    )
    window_readings_failed = sum(1 for reading in failed if reading_inside_window(reading, window))
    summary: dict[str, Any] = {
        "generator": GENERATOR,
        "schema": SUMMARY_SCHEMA,
        "profile": profile,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "compose_services": services,
        "load_step": {
            "locustfile": "loadtest/locustfile.py",
            "users": LOAD_USERS,
            "spawn_rate": LOAD_SPAWN_RATE,
            "run_seconds": LOAD_SECONDS,
        },
        "run_seconds": round(run_seconds, 1),
        "readings_submitted": len(readings),
        "readings_completed": sum(1 for reading in readings if reading.state == "COMPLETED"),
        "readings_failed": len(failed),
        "submissions": {
            "count": len(submissions),
            "failed": sum(1 for entry in submissions if not entry["ok"]),
        },
        "status_reads": {
            "count": len(status_reads),
            "failed": sum(1 for entry in status_reads if not entry["ok"]),
        },
        "readings_p50_ms": percentile(successful_submissions, 0.50),
        "readings_p95_ms": percentile(successful_submissions, 0.95),
        "status_p50_ms": percentile(successful_reads, 0.50),
        "status_p95_ms": percentile(successful_reads, 0.95),
        "throughput_per_second": round(len(terminal) / run_seconds, 2),
        "failure_window": {
            "fault": FAULT,
            "started_at": datetime.fromtimestamp(window[0], UTC).isoformat(timespec="milliseconds"),
            "ended_at": datetime.fromtimestamp(window[1], UTC).isoformat(timespec="milliseconds"),
            "started_offset_seconds": round(window[0] - started_at, 1),
            "ended_offset_seconds": round(window[1] - started_at, 1),
            "errors": {
                "submissions_failed": window_submissions_failed,
                "status_reads_failed": window_reads_failed,
                "readings_failed": window_readings_failed,
            },
        },
        "failure_window_errors": (
            window_submissions_failed + window_reads_failed + window_readings_failed
        ),
        "sampled_traces": sampled,
    }
    summary["digest"] = digest(summary)
    return summary


# --- the traces ------------------------------------------------------------------------------


def choose_samples(readings: list[Reading], window: tuple[float, float]) -> list[Reading]:
    """Pick a few readings from inside the failure window and a few from outside it.

    Inside, readings that ended ``FAILED`` come first, because their summarize span shows
    the failure; outside, readings accepted before the window opened come first, because
    they show the profile without it.
    """
    inside = [reading for reading in readings if reading_inside_window(reading, window)]
    outside = [reading for reading in readings if not reading_inside_window(reading, window)]
    inside.sort(key=lambda reading: (reading.state != "FAILED", reading.accepted_at))
    outside.sort(key=lambda reading: (reading.accepted_at >= window[0], reading.accepted_at))
    return inside[:SAMPLES_PER_SIDE] + outside[:SAMPLES_PER_SIDE]


def find_trace(
    client: httpx.Client, service: str, exception_id: str, deadline: float
) -> str | None:
    """Return the most recent Jaeger trace id carrying one exception's tag, waiting for export."""
    tags = quote(json.dumps({"coldline.exception_id": exception_id}, separators=(",", ":")))
    endpoint = f"/api/traces?service={service}&tags={tags}&limit=20&lookback=1h"
    while True:
        try:
            response = client.get(endpoint)
            response.raise_for_status()
            traces = response.json().get("data", [])
        except (httpx.HTTPError, ValueError, AttributeError):
            traces = []
        candidates: list[tuple[int, str]] = []
        for trace in traces:
            if not isinstance(trace, dict):
                continue
            trace_id = trace.get("traceID")
            spans = trace.get("spans")
            if not isinstance(trace_id, str) or not isinstance(spans, list):
                continue
            start_times = [
                span["startTime"]
                for span in spans
                if isinstance(span, dict) and isinstance(span.get("startTime"), int)
            ]
            candidates.append((max(start_times, default=0), trace_id))
        if candidates:
            return max(candidates)[1]
        if time.time() >= deadline:
            return None
        time.sleep(1.0)


def sample_traces(
    profile: str, readings: list[Reading], window: tuple[float, float], started_at: float
) -> list[dict[str, Any]]:
    """Look up one trace per chosen reading and label it inside or outside the window."""
    jaeger_port = _host_port("COLDLINE_JAEGER_HOST_PORT", 16686)
    jaeger = f"http://localhost:{jaeger_port}"
    deadline = time.time() + TRACE_WAIT_SECONDS
    sampled: list[dict[str, Any]] = []
    with httpx.Client(base_url=jaeger, timeout=5.0) as client:
        for reading in choose_samples(readings, window):
            trace_id = find_trace(client, TRACE_SERVICE[profile], reading.exception_id, deadline)
            if trace_id is None:
                continue
            sampled.append(
                {
                    "trace_id": trace_id,
                    "exception_id": reading.exception_id,
                    "window": "inside" if reading_inside_window(reading, window) else "outside",
                    "state": reading.state,
                    "failure_reason": reading.failure_reason,
                    "accepted_offset_seconds": round(reading.accepted_at - started_at, 1),
                    "jaeger_url": f"{jaeger}/trace/{trace_id}",
                }
            )
    labels = {entry["window"] for entry in sampled}
    if labels != {"inside", "outside"}:
        raise TopologyRunError(
            "Jaeger returned no trace for the sampled readings on at least one side of the "
            f"failure window (found: {', '.join(sorted(labels)) or 'none'}); check that Jaeger "
            f"is up at {jaeger} and rerun"
        )
    return sampled


# --- the run -----------------------------------------------------------------------------------


def _log(message: str) -> None:
    """Print one progress line on standard error; the summary goes to the file."""
    print(message, file=sys.stderr, flush=True)


def _drive_failure_window(profile: str, started_at: float) -> tuple[float, float]:
    """Apply the supplied fault partway through the load step and lift it again.

    The window opens when the fault control confirms the fault is applied and closes when
    it confirms it is lifted. The lift runs in ``finally``: an interrupted run never leaves
    the emulator stalled.
    """
    _log(f"load step running for {LOAD_SECONDS:.0f} s; do not touch the stack")
    time.sleep(max(0.0, started_at + FAULT_APPLY_AT_SECONDS - time.time()))
    fault_control(profile, "apply", FAULT)
    opened = time.time()
    _log(f"provider fault {FAULT} applied at +{opened - started_at:.1f} s")
    try:
        time.sleep(max(0.0, started_at + FAULT_LIFT_AT_SECONDS - time.time()))
    finally:
        fault_control(profile, "lift")
        closed = time.time()
        _log(f"provider fault {FAULT} lifted at +{closed - started_at:.1f} s")
    return opened, closed


def _wait_to_settle(
    process: subprocess.Popen[str], reader: threading.Thread, log: RunLog, started_at: float
) -> tuple[list[Reading], float]:
    """Wait for the load step to end and every accepted reading to reach a terminal state."""
    remaining = started_at + LOAD_SECONDS + LOAD_STEP_GRACE_SECONDS - time.time()
    try:
        process.wait(timeout=max(0.0, remaining))
    except subprocess.TimeoutExpired:
        process.kill()
        raise TopologyRunError("the load step did not stop on time; rerun") from None
    reader.join(timeout=5.0)
    if process.returncode != 0:
        detail = "\n".join(log.load_step_errors[-10:]) or "no detail"
        raise TopologyRunError(f"the load step failed (exit {process.returncode}):\n{detail}")
    if not log.readings:
        raise TopologyRunError("the load step accepted no readings; check the API and rerun")
    _log(
        f"load step done: {len(log.submissions)} requests, {len(log.readings)} readings "
        "accepted; waiting for them to settle"
    )
    deadline = started_at + LOAD_SECONDS + SETTLE_TIMEOUT_SECONDS
    while log.pending() and time.time() < deadline:
        time.sleep(STATUS_POLL_INTERVAL_SECONDS)
    pending = log.pending()
    if pending:
        raise TopologyRunError(
            f"{len(pending)} reading(s) never reached a terminal state within "
            f"{SETTLE_TIMEOUT_SECONDS:.0f} s of the load step ending "
            f"(for example {pending[0].exception_id}); rerun"
        )
    with log.lock:
        readings = list(log.readings.values())
    settled_at = max(reading.terminal_at or started_at for reading in readings)
    return readings, settled_at


def run() -> Path:
    """Run the whole experiment against the running profile and return the summary path."""
    profile = detect_profile()
    services = sorted(running_services(compose_records()))
    api_port = _host_port("COLDLINE_API_HOST_PORT", 8000)
    base_url = f"http://localhost:{api_port}"
    _log(f"profile {profile}: containers {', '.join(services)}; API at {base_url}")
    lifted = fault_control(profile, "status")
    if lifted != "none":
        _log(f"lifting a leftover provider fault ({lifted}) before the run")
    fault_control(profile, "lift")
    require_ready(base_url)

    log = RunLog()
    stop = threading.Event()
    started_at = time.time()
    process, reader = start_load_step(base_url, log)
    poller = threading.Thread(
        target=poll_statuses, args=(base_url, log, stop), name="status-poller", daemon=True
    )
    poller.start()
    try:
        window = _drive_failure_window(profile, started_at)
        readings, settled_at = _wait_to_settle(process, reader, log, started_at)
    finally:
        # Whatever ended the run, leave nothing behind: no load step still sending, no
        # poller still reading. The fault itself is lifted inside _drive_failure_window.
        stop.set()
        if process.poll() is None:
            process.kill()
        poller.join(timeout=STATUS_READ_TIMEOUT_SECONDS * 4)
    _log(f"settled: {len(readings)} readings terminal {settled_at - started_at:.1f} s after start")

    sampled = sample_traces(profile, readings, window, started_at)
    summary = build_summary(
        profile=profile,
        services=services,
        started_at=started_at,
        settled_at=settled_at,
        window=window,
        log=log,
        sampled=sampled,
    )
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    path = SUMMARY_DIR / f"{profile}-run.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    """Run the experiment and print the summary it wrote."""
    try:
        path = run()
    except TopologyRunError as exc:
        print(f"topology run failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("topology run interrupted; the fault was lifted, rerun when ready", file=sys.stderr)
        return 130
    summary = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(summary, indent=2, sort_keys=True))
    _log(
        f"wrote {path.relative_to(TASK_ROOT).as_posix()}: readings p95 "
        f"{summary['readings_p95_ms']} ms, status p95 {summary['status_p95_ms']} ms, "
        f"{summary['throughput_per_second']} readings/s, "
        f"{summary['failure_window_errors']} error(s) inside the failure window"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
