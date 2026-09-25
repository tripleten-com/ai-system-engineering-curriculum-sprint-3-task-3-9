"""Coldline.

===================

File:              tests/smoke/readiness.py
Component:         Smoke tests — Readiness
Purpose:           Check the documented ready state for every runtime surface, in either profile.
Interacts With:    Running Docker Compose services
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Readiness, provisioning, bounded diagnostics, topology profiles
Tools:             Python 3.12, pytest, Prometheus
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol

import httpx

from tests.runtime_config import host_port

ENDPOINTS = {
    "api": f"http://localhost:{host_port('COLDLINE_API_HOST_PORT', 8000)}/health/ready",
    "grafana": f"http://localhost:{host_port('COLDLINE_GRAFANA_HOST_PORT', 3000)}/api/health",
    "prometheus": f"http://localhost:{host_port('COLDLINE_PROMETHEUS_HOST_PORT', 9090)}/-/ready",
    "jaeger": f"http://localhost:{host_port('COLDLINE_JAEGER_HOST_PORT', 16686)}/",
    "localstack": (
        f"http://localhost:{host_port('COLDLINE_LOCALSTACK_HOST_PORT', 4566)}/_localstack/health"
    ),
}
# Sprint 2 adds LocalStack, so every Compose query has to name that profile too — a status
# check that omits it reports the LocalStack container as absent rather than as running.
COMPOSE_PROFILES = ("--profile", "observability", "--profile", "localstack")
ROOT = Path(__file__).resolve().parents[2]
# Task 3.9 runs the worker loop in one of two containers: the split profile's `worker`,
# or the single-process profile's `single`, which hosts the API routes and the worker loop
# together (compose.single.yaml). Whichever is running is the one whose health matters.
WORKER_SERVICES = ("worker", "single")

# A readiness wait is only worth spending time on once the stack is actually up. Poll every
# surface on each pass rather than exhausting one before starting the next, so a slow service
# never hides behind an earlier one, and stop early when Compose reports nothing running at all.
ATTEMPTS = 60
DELAY = 0.5
PROGRESS_EVERY = 10
NOT_RUNNING_HINT = (
    "The Coldline stack does not appear to be running. Start it with "
    "`poe start` (or `poe start-single`), then run this check again."
)


class HttpReader(Protocol):
    """Describe the HTTP operation needed by the readiness loop."""

    def get(self, endpoint: str) -> httpx.Response:
        """Return one HTTP response."""
        ...


def _compose_records() -> list[dict[str, object]] | None:
    """Return the Compose service records, or None when Compose itself cannot answer.

    Queried with compose.yaml alone. Compose lists the single-process profile's `single`
    container here too, as a container of this project that compose.yaml does not declare.
    """
    result = subprocess.run(
        ["docker", "compose", *COMPOSE_PROFILES, "ps", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def _no_containers_running() -> bool:
    """Report whether Compose currently has no container for this project at all."""
    records = _compose_records()
    if records is None:
        return False
    return not any(record.get("State") == "running" for record in records)


def _endpoint_error(client: HttpReader, endpoint: str) -> str | None:
    """Return an error string unless the endpoint answers successfully right now."""
    try:
        response = client.get(endpoint)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return str(exc)
    return None


def _wait_for_endpoints(
    client: HttpReader,
    *,
    endpoints: dict[str, str] | None = None,
    attempts: int = ATTEMPTS,
    delay: float = DELAY,
) -> dict[str, str]:
    """Poll every endpoint together until all answer, the stack is absent, or attempts expire."""
    pending = dict(ENDPOINTS if endpoints is None else endpoints)
    errors = {component: "endpoint did not answer" for component in pending}
    for attempt in range(attempts):
        for component, endpoint in list(pending.items()):
            error = _endpoint_error(client, endpoint)
            if error is None:
                del pending[component]
                errors.pop(component, None)
            else:
                errors[component] = error
        if not pending:
            return {}
        # Ask Compose on the first pass, so a student who never started the stack is answered
        # at once, then only occasionally — a cold start would otherwise pay for a subprocess
        # on every one of the sixty passes it legitimately needs.
        if attempt % PROGRESS_EVERY == 0 and _no_containers_running():
            return errors
        if attempt + 1 < attempts:
            if attempt % PROGRESS_EVERY == 0:
                waiting = ", ".join(sorted(pending))
                print(f"Waiting for {waiting} ... ({attempt + 1}/{attempts})", flush=True)
            time.sleep(delay)
    return errors


def main() -> int:
    """Return success when all documented endpoints answer successfully."""
    failures: list[str] = []
    with httpx.Client(timeout=5.0, follow_redirects=True) as client:
        endpoint_errors = _wait_for_endpoints(client)
    failures.extend(f"{component}: {error}" for component, error in sorted(endpoint_errors.items()))
    if not failures:
        worker_error = _worker_health_error()
        if worker_error is not None:
            failures.append(f"worker: {worker_error}")
    if failures:
        print("Ready-state check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        if _no_containers_running():
            print(NOT_RUNNING_HINT, file=sys.stderr)
        return 1
    print(
        "Coldline ready: API, worker dependencies, LocalStack S3, Grafana, Prometheus, and "
        "Jaeger are available."
    )
    return 0


def _worker_health_error(*, attempts: int = 60, delay: float = 0.5) -> str | None:
    """Return an error unless Compose reports a dependency-ready worker loop.

    In the split profile that is the `worker` container; in the single-process profile it
    is `single`, whose health check is the API readiness gate of the same process.
    """
    last_error = "container is not running"
    for attempt in range(attempts):
        records = _compose_records()
        if records is None:
            last_error = "Docker Compose status failed"
        else:
            worker = next(
                (record for record in records if record.get("Service") in WORKER_SERVICES), None
            )
            if worker is not None:
                if worker.get("State") == "running" and worker.get("Health") == "healthy":
                    return None
                last_error = f"container state={worker.get('State')} health={worker.get('Health')}"
            elif _no_containers_running():
                return last_error
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last_error


if __name__ == "__main__":
    raise SystemExit(main())
