"""Coldline.

===================

File:              infra/topology/load_step.py
Component:         Topology tools — Pinned load step
Purpose:           Drive the pinned Locust traffic profile and report each request as one JSON line.
Interacts With:    loadtest/locustfile.py, the running Coldline API, infra/topology/topology_run.py
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Controlled load experiments, one independent variable
Tools:             Python 3.12, Locust, gevent

The traffic shape is not defined here. It is ``ColdlineUser`` from ``loadtest/locustfile.py``,
loaded from that file exactly as ``locust -f loadtest/locustfile.py`` (``poe load-test``)
loads it, and run with the same user count, spawn rate and duration ``poe load-test`` uses.
What this module adds is the per-request record the topology run needs and Locust's summary
tables do not give: for every request, when it started, how long it took, whether it
succeeded, and which exception the API accepted, one JSON object per line on standard
output. ``topology_run.py`` starts this as its own process because Locust runs on gevent,
which patches the interpreter it runs in; the run itself stays on plain threads.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import gevent
from locust.env import Environment
from locust.log import setup_logging

TASK_ROOT = Path(__file__).resolve().parents[2]
LOCUSTFILE = TASK_ROOT / "loadtest/locustfile.py"
USER_CLASS = "ColdlineUser"


def load_user_class() -> type[Any]:
    """Load the pinned user class from the locustfile the way the Locust CLI does."""
    spec = importlib.util.spec_from_file_location("coldline_locustfile", LOCUSTFILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {LOCUSTFILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    user_class = getattr(module, USER_CLASS, None)
    if user_class is None:
        raise RuntimeError(f"{LOCUSTFILE} defines no {USER_CLASS}")
    return user_class  # type: ignore[no-any-return]


def main(argv: list[str] | None = None) -> int:
    """Run the pinned load step against one host and stream one record per request."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host", required=True, help="the API base URL, e.g. http://localhost:8000"
    )
    parser.add_argument("--users", type=int, required=True)
    parser.add_argument("--spawn-rate", type=float, required=True)
    parser.add_argument("--run-time", type=float, required=True, help="seconds")
    args = parser.parse_args(argv)
    setup_logging("WARNING")  # type: ignore[no-untyped-call]
    environment = Environment(user_classes=[load_user_class()], host=args.host)
    counts = {"requests": 0, "failures": 0}

    def on_request(
        request_type: str,
        name: str,
        response_time: float,
        response_length: int,
        response: Any,
        context: Any,
        exception: BaseException | None,
        **kwargs: Any,
    ) -> None:
        """Print one request record; the parent process reads them as they arrive."""
        status = getattr(response, "status_code", None) if response is not None else None
        exception_id: str | None = None
        if exception is None and response is not None:
            try:
                body = response.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and isinstance(body.get("exception_id"), str):
                exception_id = body["exception_id"]
        counts["requests"] += 1
        if exception is not None:
            counts["failures"] += 1
        start_time = kwargs.get("start_time")
        record = {
            "kind": "request",
            "request_type": request_type,
            "name": name,
            "start_time": float(start_time) if isinstance(start_time, int | float) else None,
            "response_time_ms": round(float(response_time), 3),
            "status": status,
            "ok": exception is None,
            "error": None if exception is None else type(exception).__name__,
            "exception_id": exception_id,
        }
        print(json.dumps(record, sort_keys=True), flush=True)

    environment.events.request.add_listener(on_request)  # type: ignore[no-untyped-call]
    runner = environment.create_local_runner()
    runner.start(args.users, spawn_rate=args.spawn_rate)
    gevent.spawn_later(args.run_time, runner.quit)
    runner.greenlet.join()
    print(json.dumps({"kind": "done", **counts}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
