# ModelProvider fidelity

The active adapter is an in-process deterministic simulation. It returns a fixed-format summary
from the supplied synthetic reading and waits for the configured local latency. It proves the
application contract, asynchronous composition, deterministic tests, and local telemetry behavior.

It does not prove hosted-model availability, output quality, token accounting, safety behavior,
provider throttling, network failure behavior, or cost. No live endpoint or credential is used.
The fixed delay is not a performance measurement, capacity test, latency target, or availability
claim.

## Fault control (Task 3.9)

The emulator carries one supplied fault control, `python -m adapters.model.faults`, read from a
flag file inside the container that hosts the worker loop. Its one fault, `stall`, makes every
provider call block its thread for a fixed few seconds, as a hanging synchronous provider client
would, and then fail terminally, so the reading ends `FAILED`. It emulates the shape of a provider
that stops answering; it does not reproduce any hosted provider's real timeout, error body,
throttling, or partial-response behavior, and a blocked thread is one way a real client hangs,
not the only one. What the stall shows about a topology (which paths share the thread it holds)
is deterministic; the latency and throughput figures measured around it on a laptop are not.
