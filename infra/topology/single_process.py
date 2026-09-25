"""Coldline.

===================

File:              infra/topology/single_process.py
Component:         Topology tools — Single-process entry
Purpose:           Run the API routes and the worker loop in one process, on one event loop.
Interacts With:    api.bootstrap, worker.bootstrap, compose.single.yaml, uvicorn
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Topology, shared process, blast radius
Tools:             Python 3.12, uvicorn, asyncio

This is the whole difference between the two profiles. The split profile runs
``uvicorn api.bootstrap:app`` in the api container and ``python -m worker.bootstrap`` in
the worker container. This entry runs the very same two compositions, unchanged, inside
one container and one Python process: the API application object from ``api.bootstrap``
is served by uvicorn as a task on the running event loop, and the worker loop composed
by ``worker.bootstrap.compose`` runs as another task on that same loop. Nothing is
patched or re-implemented; if a route or the worker changes, this profile changes with it.

What the shared process means, and what Task 3.9 measures: anything that holds the one
event loop holds both the request handlers and the worker loop. The supplied provider
fault (``adapters.model.faults``, ``stall``) blocks its thread the way a hanging
synchronous provider client does. In the split profile that thread belongs to the worker
container and the API answers throughout; here it is the thread uvicorn serves from, so
status reads and submissions wait, and time out, for as long as the provider is stalled.

Compose runs this file through ``compose.single.yaml`` (``poe start-single``); it is not
meant to be started by hand. The API stays on port 8000 inside the container, so the same
host port and the same ``/health/ready`` gate apply.
"""

import asyncio
import logging

import uvicorn
from opentelemetry import trace
from prometheus_client import start_http_server

from api.bootstrap import app
from worker.bootstrap import compose
from worker.config import WorkerSettings
from worker.queue_monitor import poll_dead_letter_depth
from worker.runtime import run_loop

API_PORT = 8000
LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Serve the API and run the worker loop on this one event loop until either stops."""
    # api.bootstrap already configured JSON logging and the trace provider from the
    # container's COLDLINE_SERVICE_NAME when it was imported above; the worker half
    # joins the same process-wide provider, so every span carries one service name.
    settings = WorkerSettings()  # type: ignore[call-arg]  # protected environment is the source
    LOGGER.info("single-process profile starting build_version=%s", settings.build_version)
    composed = await compose(settings)
    start_http_server(settings.metrics_port)
    # log_config=None keeps api.bootstrap's JSON logging; uvicorn's default config would
    # reinstall its own handlers on top of it.
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=API_PORT, log_config=None))
    api_task = asyncio.create_task(server.serve(), name="api")
    worker_task = asyncio.create_task(
        run_loop(
            composed.queue,
            composed.application,
            trace.get_tracer("worker.bootstrap"),
            stale_message_ms=settings.stale_message_ms,
        ),
        name="worker",
    )
    monitor_task = asyncio.create_task(
        poll_dead_letter_depth(composed.sqs_client, composed.dead_letter_queue_url),
        name="dead-letter-monitor",
    )
    try:
        # uvicorn owns the SIGTERM/SIGINT handlers: a stop signal ends `serve()`, which
        # ends the wait below, and the worker half is cancelled with it. A worker loop
        # that ever exits on its own ends the process the same way, so Compose restarts
        # the whole container rather than leaving an API with no consumer behind it.
        done, _ = await asyncio.wait({api_task, worker_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        server.should_exit = True
        worker_task.cancel()
        monitor_task.cancel()
        await asyncio.gather(api_task, worker_task, monitor_task, return_exceptions=True)
        await composed.pool.close()


if __name__ == "__main__":
    asyncio.run(main())
