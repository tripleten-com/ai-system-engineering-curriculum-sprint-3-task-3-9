"""Coldline.

===================

File:              tests/contract/topology_contract.py
Component:         Contract tests — Topology helpers
Purpose:           Read the two run summaries, the answer sheet, and the running profile.
Interacts With:    docs/student/topology/*.json, submission.yaml, Docker Compose, the fault control
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Generated evidence, content digest, topology profiles
Tools:             Python 3.12, Docker Compose

The checks never import the topology runner. They read the summaries it wrote exactly as a
student commits them, recompute the content digest the same way the runner did, and read
the answer sheet beside them, so what they assert is what the files show.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, TypeGuard, cast

import yaml

TASK_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_DIR = TASK_ROOT / "docs/student/topology"
PROFILES = ("split", "single")
GENERATOR = "poe topology-run"
# The four figures copied from a summary into answers.runs.<profile>, compared as written.
RUN_FIELDS = ("readings_p95_ms", "status_p95_ms", "throughput_per_second", "failure_window_errors")
DIMENSIONS = ("latency", "throughput", "blast_radius")
SPLIT_EFFECTS = ("helped", "hurt", "no_clear_difference")
EVIDENCE = ("summaries", "traces", "both")
DECISIONS = ("keep_split", "run_single", "not_settled")
WINDOW_LABELS = ("inside", "outside")
# The first-party Compose services each profile runs while its summary is being written.
PROFILE_SERVICES = {"split": ["api", "worker"], "single": ["single"]}
FAULT_HOST_SERVICE = {"split": "worker", "single": "single"}
COMPOSE_PROFILES = ("--profile", "observability", "--profile", "localstack")
SINGLE_FILES = ("-f", "compose.yaml", "-f", "compose.single.yaml")
TRACE_ID = re.compile(r"^[0-9a-f]{16,32}$")
# The summary fields the topology run writes and the checks read, with the JSON types they
# must carry. Extra descriptive fields are allowed; these are required.
NUMERIC_FIELDS = ("readings_p95_ms", "status_p95_ms", "throughput_per_second", "run_seconds")


class TopologyCheckError(ValueError):
    """Report one actionable topology-evidence failure."""


def summary_path(profile: str) -> Path:
    """Return where `poe topology-run` writes one profile's summary."""
    return SUMMARY_DIR / f"{profile}-run.json"


def load_summary(profile: str) -> dict[str, Any] | None:
    """Return one profile's summary as written, or None when it does not exist or is not JSON."""
    path = summary_path(profile)
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else None


def digest(summary: dict[str, Any]) -> str:
    """Return the content digest of a summary, over everything but the digest itself.

    Identical to ``infra/topology/topology_run.py``'s ``digest``; the two must stay the same,
    because a summary whose digest no longer matches its content is one that was edited.
    """
    body = {key: value for key, value in summary.items() if key != "digest"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_number(value: object) -> TypeGuard[int | float]:
    """Return whether one JSON value is a real number (a bool is not)."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def summary_problems(summary: dict[str, Any] | None, profile: str) -> list[str]:
    """Return every reason one summary is not what `poe topology-run` writes for that profile."""
    name = summary_path(profile).relative_to(TASK_ROOT).as_posix()
    if summary is None:
        return [f"{name} is missing or is not one JSON object; run `poe topology-run`"]
    problems: list[str] = []
    if summary.get("generator") != GENERATOR:
        problems.append(f"{name} was not written by {GENERATOR}")
    if summary.get("profile") != profile:
        problems.append(f"{name} names profile {summary.get('profile')!r}, not {profile!r}")
    if summary.get("digest") != digest(summary):
        problems.append(f"{name} has been edited since {GENERATOR} wrote it (digest mismatch)")
    if summary.get("compose_services") != PROFILE_SERVICES[profile]:
        problems.append(
            f"{name} was written against containers {summary.get('compose_services')!r}, "
            f"not the {profile} profile's {PROFILE_SERVICES[profile]!r}"
        )
    for field_name in NUMERIC_FIELDS:
        value = summary.get(field_name)
        if not _is_number(value) or value <= 0:
            problems.append(f"{name}: {field_name} must be a positive number")
    errors = summary.get("failure_window_errors")
    if not isinstance(errors, int) or isinstance(errors, bool) or errors < 0:
        problems.append(f"{name}: failure_window_errors must be a whole number")
    window = summary.get("failure_window")
    run_seconds = summary.get("run_seconds")
    if not isinstance(window, dict):
        problems.append(f"{name}: failure_window is missing")
    else:
        started = window.get("started_offset_seconds")
        ended = window.get("ended_offset_seconds")
        if _is_number(started) and _is_number(ended) and _is_number(run_seconds):
            if not 0 <= started < ended <= run_seconds:
                problems.append(f"{name}: the failure window must start and end inside the run")
        else:
            problems.append(f"{name}: failure_window offsets must be numbers")
        for stamp in ("started_at", "ended_at"):
            if not isinstance(window.get(stamp), str):
                problems.append(f"{name}: failure_window.{stamp} is missing")
    sampled = summary.get("sampled_traces")
    if not isinstance(sampled, list) or not sampled:
        problems.append(f"{name}: sampled_traces must list at least one trace")
    else:
        for entry in sampled:
            trace_id = entry.get("trace_id") if isinstance(entry, dict) else None
            label = entry.get("window") if isinstance(entry, dict) else None
            if not isinstance(trace_id, str) or not TRACE_ID.match(trace_id):
                problems.append(f"{name}: a sampled trace id is not a Jaeger trace id")
            if label not in WINDOW_LABELS:
                problems.append(f"{name}: a sampled trace is not labelled inside or outside")
    return problems


def sampled_trace_ids(summary: dict[str, Any]) -> set[str]:
    """Return every trace id one summary sampled."""
    sampled = summary.get("sampled_traces")
    if not isinstance(sampled, list):
        return set()
    return {
        str(entry["trace_id"])
        for entry in sampled
        if isinstance(entry, dict) and isinstance(entry.get("trace_id"), str)
    }


def load_answers() -> dict[str, Any]:
    """Load the recorded answers; a blank sheet still lets every check run and report."""
    document = yaml.safe_load((TASK_ROOT / "submission.yaml").read_text(encoding="utf-8"))
    recorded = document.get("answers") if isinstance(document, dict) else None
    return recorded if isinstance(recorded, dict) else {}


def mapping(container: dict[str, Any], key: str) -> dict[str, Any]:
    """Return one nested answers mapping, or an empty mapping when it is absent or not one."""
    value = container.get(key)
    return value if isinstance(value, dict) else {}


def compose_records() -> list[dict[str, Any]]:
    """Return every Compose container record for this project, orphans included."""
    result = subprocess.run(
        ["docker", "compose", *COMPOSE_PROFILES, "ps", "--all", "--format", "json"],
        cwd=TASK_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise TopologyCheckError(f"docker compose ps failed: {result.stderr.strip()}")
    text = result.stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        return cast(list[dict[str, Any]], json.loads(text))
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def running_profile() -> str | None:
    """Name the profile whose first-party containers are running, or None."""
    running = {
        str(record.get("Service"))
        for record in compose_records()
        if record.get("State") == "running" and record.get("Service") in {"api", "worker", "single"}
    }
    if running == {"api", "worker"}:
        return "split"
    if running == {"single"}:
        return "single"
    return None


def fault_status(profile: str) -> str:
    """Ask the emulator's fault control, inside the running profile, which fault is active."""
    files = SINGLE_FILES if profile == "single" else ()
    result = subprocess.run(
        [
            "docker",
            "compose",
            *files,
            *COMPOSE_PROFILES,
            "exec",
            "-T",
            FAULT_HOST_SERVICE[profile],
            "python",
            "-m",
            "adapters.model.faults",
            "status",
        ],
        cwd=TASK_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise TopologyCheckError(
            f"the fault control did not answer in the {FAULT_HOST_SERVICE[profile]} container: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()
