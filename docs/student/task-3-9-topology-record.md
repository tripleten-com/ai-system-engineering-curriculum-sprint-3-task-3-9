# Task 3.9 topology record

This record is the answer Dana takes to the budget review: what the two profiles did under
the same load and the same provider failure, and what that means for the dispatch floor. It
is not graded by the automated checks; they read `submission.yaml` and the two generated
summaries. Replace every italic placeholder line below with your own evidence; `poe verify`
fails while any placeholder remains. Paste each summary exactly as `poe topology-run` wrote
it, name the trace you read, and keep the outputs yours: every figure and every trace id here
comes from your own runs on your own machine.

## Step 1 - Split profile

The `docker compose --profile observability --profile localstack ps` output showing separate
`api` and `worker` containers, then `docs/student/topology/split-run.json` as written, and
one or two sentences on what you noticed: what the failure window looked like in the
topology Coldline runs today, and how long the run took to settle.

`docker compose --profile observability --profile localstack ps` before the run (first-party
services only; the observability and emulator services are omitted for width):

```text
NAME                                     IMAGE                    SERVICE   STATUS
ais-...-api-1                            coldline-api:3.1.0       api       Up 27 seconds (healthy)
ais-...-worker-1                         coldline-worker:3.1.0    worker    Up 27 seconds (healthy)
```

`api` and `worker` are two separate containers, each with its own health state, which is the
split profile as Coldline runs it today.

`docs/student/topology/split-run.json`, exactly as `poe topology-run` wrote it:

```json
{
  "compose_services": [
    "api",
    "worker"
  ],
  "digest": "sha256:9b78bd00cac61d6d60c790b181d2feea0ce87b2b2780031fb012cface66196f4",
  "failure_window": {
    "ended_at": "2026-09-28T10:00:58.279+00:00",
    "ended_offset_seconds": 21.2,
    "errors": {
      "readings_failed": 4,
      "status_reads_failed": 0,
      "submissions_failed": 0
    },
    "fault": "stall",
    "started_at": "2026-09-28T10:00:49.967+00:00",
    "started_offset_seconds": 12.9
  },
  "failure_window_errors": 4,
  "generator": "poe topology-run",
  "load_step": {
    "locustfile": "loadtest/locustfile.py",
    "run_seconds": 30.0,
    "spawn_rate": 2.0,
    "users": 2
  },
  "profile": "split",
  "readings_completed": 33,
  "readings_failed": 4,
  "readings_p50_ms": 21.4,
  "readings_p95_ms": 2081.4,
  "readings_submitted": 37,
  "recorded_at": "2026-09-28T10:01:22+00:00",
  "run_seconds": 32.8,
  "sampled_traces": [
    {
      "accepted_offset_seconds": 13.2,
      "exception_id": "exc-ef29e777-d513-560f-bd91-8c1343779855",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/3e68e06966d636a79788c8ce6e6159a6",
      "state": "FAILED",
      "trace_id": "3e68e06966d636a79788c8ce6e6159a6",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 13.3,
      "exception_id": "exc-10a49d39-5a45-56b3-b79a-430a19f5009c",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/54adc75f98128a3ab79ac5c3883c205a",
      "state": "FAILED",
      "trace_id": "54adc75f98128a3ab79ac5c3883c205a",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 14.4,
      "exception_id": "exc-640ae532-34a7-5188-b2ce-ff1ca6a49a45",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/ad82a70eb94da146e3a1ee0bd24c49a9",
      "state": "FAILED",
      "trace_id": "ad82a70eb94da146e3a1ee0bd24c49a9",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 8.7,
      "exception_id": "exc-72c8e12a-5aba-5d26-bd17-efd739c28f2b",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/1e20bb2b1067b144d9e2720f1041b57e",
      "state": "COMPLETED",
      "trace_id": "1e20bb2b1067b144d9e2720f1041b57e",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 9.0,
      "exception_id": "exc-f273525d-3c98-558b-8cd7-5872e062b19b",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/a9233094adefacd439854ef60759188b",
      "state": "COMPLETED",
      "trace_id": "a9233094adefacd439854ef60759188b",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 12.1,
      "exception_id": "exc-50d7d8bd-b56d-5c1f-a878-11a4fa967a05",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/ccc4bb2b3c14fdcf28945ac358251d2d",
      "state": "COMPLETED",
      "trace_id": "ccc4bb2b3c14fdcf28945ac358251d2d",
      "window": "outside"
    }
  ],
  "schema": "coldline-topology-run/1",
  "status_p50_ms": 4.2,
  "status_p95_ms": 8.4,
  "status_reads": {
    "count": 273,
    "failed": 0
  },
  "submissions": {
    "count": 37,
    "failed": 0
  },
  "throughput_per_second": 1.13
}
```

What I noticed: the failure window opened 12.9 s into the run and closed at 21.2 s, and
everything it broke was on the summary side — four readings ended `FAILED` with
`model_provider_terminal_failure`, while `submissions_failed` and `status_reads_failed` were
both 0. The dispatch floor never saw it: all 37 submissions and all 273 status reads
succeeded, and status reads stayed fast throughout (p50 4.2 ms, p95 8.4 ms). Submission
latency is the one thing that is not flat — p50 21.4 ms against p95 2081.4 ms, so roughly two
of the 37 submissions took about two seconds; I come back to where that time went in the
comparison, because the split profile's API shares no thread with the stalled provider. The
run settled quickly: `run_seconds` 32.8 for a 30 s load step, so the last accepted reading
reached a terminal state under three seconds after the load stopped, and the stack needed no
help to come back after the fault was lifted.

## Step 2 - Single-process profile

The `docker compose ps` output showing one `single` container where `api` and `worker` were,
then `docs/student/topology/single-run.json` as written, and anything that differed in how
the run itself behaved: how long it took to settle, and whether the stack came back after the
failure without help. If you reran a profile, say which run you kept and why.

`docker compose --profile observability --profile localstack ps` after `poe start-single`
(first-party services only):

```text
NAME                                     IMAGE                    SERVICE   STATUS
ais-...-single-1                         coldline-api:3.1.0       single    Up 24 seconds (healthy)
```

No `api` and no `worker` container: one `single` container from the api image, command
`python infra/topology/single_process.py`, publishing the API on the same host port 8000.

`docs/student/topology/single-run.json`, exactly as `poe topology-run` wrote it:

```json
{
  "compose_services": [
    "single"
  ],
  "digest": "sha256:ee33da13a487c2556481467311acff99301a99bd47ebe7bf6b01981c8a7e4863",
  "failure_window": {
    "ended_at": "2026-09-28T10:04:01.012+00:00",
    "ended_offset_seconds": 20.8,
    "errors": {
      "readings_failed": 4,
      "status_reads_failed": 4,
      "submissions_failed": 0
    },
    "fault": "stall",
    "started_at": "2026-09-28T10:03:51.071+00:00",
    "started_offset_seconds": 10.9
  },
  "failure_window_errors": 8,
  "generator": "poe topology-run",
  "load_step": {
    "locustfile": "loadtest/locustfile.py",
    "run_seconds": 30.0,
    "spawn_rate": 2.0,
    "users": 2
  },
  "profile": "single",
  "readings_completed": 32,
  "readings_failed": 4,
  "readings_p50_ms": 27.7,
  "readings_p95_ms": 2096.1,
  "readings_submitted": 36,
  "recorded_at": "2026-09-28T10:04:23+00:00",
  "run_seconds": 31.3,
  "sampled_traces": [
    {
      "accepted_offset_seconds": 11.7,
      "exception_id": "exc-73a30731-3008-584b-9fd3-31a42abc60b5",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/f5b514f46c0a96fa108246f33083d7c7",
      "state": "FAILED",
      "trace_id": "f5b514f46c0a96fa108246f33083d7c7",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 11.8,
      "exception_id": "exc-8091b246-9906-5766-8f1b-c4326c3d398c",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/60568056fc835e0498042b03948af91e",
      "state": "FAILED",
      "trace_id": "60568056fc835e0498042b03948af91e",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 12.9,
      "exception_id": "exc-cbd620eb-299a-5dde-9058-631b4d811146",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/e019cc4a6b62bb1da3e449409245cca7",
      "state": "FAILED",
      "trace_id": "e019cc4a6b62bb1da3e449409245cca7",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 1.2,
      "exception_id": "exc-598fbf95-dd48-5ff4-a74a-54a7be370620",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/13aa6d6c9ef31760d85310e647d6f443",
      "state": "COMPLETED",
      "trace_id": "13aa6d6c9ef31760d85310e647d6f443",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 1.2,
      "exception_id": "exc-a12b2505-c74e-5768-8b0c-ba99c93915a8",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/f45b495029ab16d8e82a47c6bc06764e",
      "state": "COMPLETED",
      "trace_id": "f45b495029ab16d8e82a47c6bc06764e",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 4.3,
      "exception_id": "exc-e42f3b02-a627-5f00-923c-12d9e7d0cc03",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/3af86860d51c25352c2e70303f59e122",
      "state": "COMPLETED",
      "trace_id": "3af86860d51c25352c2e70303f59e122",
      "window": "outside"
    }
  ],
  "schema": "coldline-topology-run/1",
  "status_p50_ms": 4.9,
  "status_p95_ms": 1021.4,
  "status_reads": {
    "count": 67,
    "failed": 4
  },
  "submissions": {
    "count": 36,
    "failed": 0
  },
  "throughput_per_second": 1.15
}
```

What differed in how the run behaved: the run itself settled slightly faster (`run_seconds`
31.3 against 32.8), and the stack recovered on its own once the fault was lifted at 20.8 s —
no restart, no manual step, and the readings accepted after the window completed normally.
What changed is what the failure reached. In the split run the status-read path was
untouched; here `status_reads_failed` is 4 and `status_p95_ms` is 1021.4 ms, which is the
runner's 1 s status-read timeout, so those reads did not just slow down, they timed out. The
number of status reads the runner got through in the same 30 s collapsed from 273 to 67:
while the provider stalled, the one event loop that serves the API was also the loop the
worker's blocking provider call held, so dispatcher-facing reads queued behind it. The
summary side failed the same way in both runs (4 readings `FAILED`), so the extra 4 errors in
`failure_window_errors` (8 against 4) are all on the dispatch side.

I ran each profile once and kept both runs; neither was interrupted, both `poe topology-run`
invocations exited 0 after `poe ready` reported the stack ready, and no shell setting or port
override changed between them.

## Comparison

One paragraph per dimension, each naming the figures from both summaries and the trace it
rests on. Latency: `readings_p95_ms` and `status_p95_ms` side by side. Throughput:
`throughput_per_second` side by side. Blast radius: the errors inside each failure window and
which kind they were (failed submissions, failed status reads, readings that ended `FAILED`).
Then the trace pair: which service names appear in each, where the accept span ends and where
`coldline.process_exception` and `model_provider.summarize` begin, and what the failure did to
the summarize span. Close with one sentence on what these two runs cannot show.

**Latency.** Reading submissions came in the same in both profiles: `readings_p95_ms` 2081.4 ms
split against 2096.1 ms single, a 0.7 % gap, with `readings_p50_ms` 21.4 ms against 27.7 ms.
Those p95 values are not the server's doing. Searching Jaeger for every root
`POST /api/v1/readings` span of each run returns 37 spans for `coldline-api` (slowest 51.5 ms)
and 36 for `coldline-single` (slowest 117.5 ms, two of them at 10:03:54.44, inside the failure
window). So the ~2 s tail both runs report sits outside the server span — the first request of
each of the two load users pays connection setup — and it is present in both profiles equally.
Status reads are where the two profiles separate: `status_p95_ms` 8.4 ms split against
1021.4 ms single, with `status_p50_ms` 4.2 ms against 4.9 ms. 1021.4 ms is the runner's 1 s
per-operation status-read timeout being reached and only just survived; the median shows the
path itself is still fast when the loop is free. The trace pair confirms the accept path is
never where the time goes: 14.6 ms in the split trace, 23.6 ms in the single one, against
2503.5 ms and 2501.8 ms in `model_provider.summarize`.

**Throughput.** `throughput_per_second` 1.13 split against 1.15 single, from
`readings_submitted` 37 against 36. Every accepted reading reached a terminal state in both
runs (33 completed + 4 failed, and 32 completed + 4 failed), and the runs settled in 32.8 s and
31.3 s. The load step sends its next reading only when the previous response comes back, so the
one fewer submission in the single run lowers its own denominator too; a 1.8 % difference
between two 30 s runs on one laptop is noise, not a finding. Neither profile built a backlog it
could not drain, and neither needed help after the fault was lifted.

**Blast radius.** `failure_window_errors` 4 split against 8 single, and the kinds are what
matter. Split: `readings_failed` 4, `submissions_failed` 0, `status_reads_failed` 0 — the
failure stayed entirely on the summary side, and 273 status reads completed over the run
without one failure. Single: the same `readings_failed` 4, still `submissions_failed` 0, but
`status_reads_failed` 4, and the number of status reads the runner completed at all fell from
273 to 67. That collapse is the real measure: while the provider stalled, the reads dispatchers
depend on were queued behind it rather than answered. The stall is 2.5 s of blocked thread per
call and four calls met it, so it covered nearly the whole 9.9 s window.

**The trace pair.** Split `3e68e06966d636a79788c8ce6e6159a6` (inside window, `FAILED`,
`model_provider_terminal_failure`) and single `f5b514f46c0a96fa108246f33083d7c7` (inside window,
same state and reason). Both carry 14 spans in the same order. In the split trace the accept
side is `coldline-api`: `POST /api/v1/readings` runs 14.6 ms and ends 202 after
`postgres.exceptions.create`, `postgres.exceptions.transition` and `job_queue.publish`; then
`coldline-worker` picks the job up 7 ms later, `coldline.process_exception` opens at +21.6 ms and
`model_provider.summarize` at +26.6 ms, holds 2503.5 ms and closes with
`otel.status_code=ERROR`, `TerminalProviderError: provider emulator fault: stall held the call
for 2.5 s and then failed`; one more `postgres.exceptions.transition` writes the terminal state.
The single trace is the same picture with the same figures — accept 23.6 ms,
`coldline.process_exception` at +29.1 ms, `model_provider.summarize` at +32.9 ms for 2501.8 ms,
the same terminal error, no retry — and it differs only in that every span carries one service
name, `coldline-single`, where the split trace carries two. That is exactly what the pair shows:
the topology does not change what happens to one reading, and it does not change how the
provider fails. It changes whose process is holding still for 2.5 s, and the price of that shows
up in the other requests the summaries count, not in this trace.

**What these two runs cannot show.** They are two 30 s samples on one laptop with one injected
fault, so they say nothing about cost in money, about behaviour across hosts or under production
traffic, about a provider that is slow rather than terminally stalled, or about whether the same
gap survives more load; a longer run on a dedicated host, repeated several times per profile,
would be needed before treating the latency and throughput figures as anything but noise.
