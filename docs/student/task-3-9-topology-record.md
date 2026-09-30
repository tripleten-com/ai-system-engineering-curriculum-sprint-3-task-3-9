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

`docker compose --profile observability --profile localstack ps` before the run (recorded
command 6), first-party containers only:

```text
NAME                     IMAGE                   COMMAND                  SERVICE   STATUS
...-api-1                coldline-api:3.1.0      "uvicorn api.bootstr…"   api       Up 31 seconds (healthy)   127.0.0.1:8000->8000/tcp
...-worker-1             coldline-worker:3.1.0   "python -m worker.bo…"   worker    Up 31 seconds (healthy)   9100/tcp
```

Separate `api` and `worker` containers, as the split profile expects. Alongside them:
`postgres`, `localstack`, `redis`, `jaeger`, `prometheus`, `grafana`, `alertmanager`.

Console output of `./.tools/bin/uv run --frozen poe topology-run` (recorded command 7):

```text
profile split: containers api, worker; API at http://localhost:8000
load step running for 30 s; do not touch the stack
provider fault stall applied at +11.4 s
provider fault stall lifted at +21.4 s
load step done: 38 requests, 38 readings accepted; waiting for them to settle
settled: 38 readings terminal 32.4 s after start
wrote docs/student/topology/split-run.json: readings p95 2096.5 ms, status p95 7.6 ms,
1.17 readings/s, 4 error(s) inside the failure window
```

`docs/student/topology/split-run.json`, exactly as `poe topology-run` wrote it:

```json
{
  "compose_services": [
    "api",
    "worker"
  ],
  "digest": "sha256:093bd903b79c46169a6c6d3e3a1546cce34f078d7d9a80019816eb001122c353",
  "failure_window": {
    "ended_at": "2026-09-30T01:27:43.287+00:00",
    "ended_offset_seconds": 21.4,
    "errors": {
      "readings_failed": 4,
      "status_reads_failed": 0,
      "submissions_failed": 0
    },
    "fault": "stall",
    "started_at": "2026-09-30T01:27:33.283+00:00",
    "started_offset_seconds": 11.4
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
  "readings_completed": 34,
  "readings_failed": 4,
  "readings_p50_ms": 23.6,
  "readings_p95_ms": 2096.5,
  "readings_submitted": 38,
  "recorded_at": "2026-09-30T01:28:07+00:00",
  "run_seconds": 32.4,
  "sampled_traces": [
    {
      "accepted_offset_seconds": 11.7,
      "exception_id": "exc-3e3efa5c-78fa-5c60-851a-5c821660978d",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/fe879f670abcbc12fce6dfeccc98d3c2",
      "state": "FAILED",
      "trace_id": "fe879f670abcbc12fce6dfeccc98d3c2",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 11.8,
      "exception_id": "exc-d9e55e8b-46e7-57c4-8364-e57ddda1b36d",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/9edc82d4d8ed59900989cb6dec8e73de",
      "state": "FAILED",
      "trace_id": "9edc82d4d8ed59900989cb6dec8e73de",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 13.1,
      "exception_id": "exc-1405135f-a85e-5545-a58b-961c27606b63",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/59345e834b2ee138d2c856d3feea5ae8",
      "state": "FAILED",
      "trace_id": "59345e834b2ee138d2c856d3feea5ae8",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 7.2,
      "exception_id": "exc-06242092-73f9-571e-80ef-c0e76e2317f9",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/536b7f175e9bc7265a2881e771d3365b",
      "state": "COMPLETED",
      "trace_id": "536b7f175e9bc7265a2881e771d3365b",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 7.2,
      "exception_id": "exc-855ad4c4-39a7-5744-9d6b-9710b366d0f1",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/d30b6594eb51a1bb3116499e6978209d",
      "state": "COMPLETED",
      "trace_id": "d30b6594eb51a1bb3116499e6978209d",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 10.5,
      "exception_id": "exc-7e4e867b-5fb9-525c-8c0f-afba19068b4c",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/cebac3f494c43f043d7f9b123e7b8d05",
      "state": "COMPLETED",
      "trace_id": "cebac3f494c43f043d7f9b123e7b8d05",
      "window": "outside"
    }
  ],
  "schema": "coldline-topology-run/1",
  "status_p50_ms": 4.4,
  "status_p95_ms": 7.6,
  "status_reads": {
    "count": 275,
    "failed": 0
  },
  "submissions": {
    "count": 38,
    "failed": 0
  },
  "throughput_per_second": 1.17
}
```

What I noticed. The failure window sat from +11.4 s to +21.4 s, inside the 30 s load step,
and it cost exactly four readings: `readings_failed: 4`, with `submissions_failed: 0` and
`status_reads_failed: 0`. So in the topology Coldline runs today the stall stayed on the
summary side — all 38 submissions and all 275 status reads still succeeded while the
provider was failing. The run settled 32.4 s after the first request, about 2 s after the
load step ended, and the stack needed no help afterwards. The one figure I did not expect
is `readings_p95_ms` 2096.5 ms against a `readings_p50_ms` of 23.6 ms: with 38 submissions
the p95 is the second-slowest request, so this is a tail of one or two slow POSTs on an
otherwise ~24 ms accept path, and on a single laptop run I cannot yet tell a cold API
worker from host noise. I keep it in mind as the noisiest of the four figures.

## Step 2 - Single-process profile

The `docker compose ps` output showing one `single` container where `api` and `worker` were,
then `docs/student/topology/single-run.json` as written, and anything that differed in how
the run itself behaved: how long it took to settle, and whether the stack came back after the
failure without help. If you reran a profile, say which run you kept and why.

`docker compose --profile observability --profile localstack ps` after `poe start-single`
(recorded command 10), first-party containers only:

```text
NAME                     IMAGE                COMMAND                  SERVICE   STATUS
...-single-1             coldline-api:3.1.0   "python infra/topolo…"   single    Up 28 seconds (healthy)   127.0.0.1:8000->8000/tcp
```

No `api` and no `worker` container: one `single` container from the api image, running
`infra/topology/single_process.py`, answering on the same host port 8000. Everything around
it (`postgres`, `localstack`, `redis`, `jaeger`, `prometheus`, `grafana`, `alertmanager`) is
the same container it was in Step 1, untouched by the profile switch.

Console output of the same `poe topology-run`, no option changed (recorded command 11):

```text
profile single: containers single; API at http://localhost:8000
load step running for 30 s; do not touch the stack
provider fault stall applied at +11.1 s
provider fault stall lifted at +21.3 s
load step done: 36 requests, 36 readings accepted; waiting for them to settle
settled: 36 readings terminal 31.2 s after start
wrote docs/student/topology/single-run.json: readings p95 2122.8 ms, status p95 1031.3 ms,
1.15 readings/s, 8 error(s) inside the failure window
```

`docs/student/topology/single-run.json`, exactly as `poe topology-run` wrote it:

```json
{
  "compose_services": [
    "single"
  ],
  "digest": "sha256:c94cf91605a06f6a883787baf3d413b140dde607a37000d36c5f599a9c5338fc",
  "failure_window": {
    "ended_at": "2026-09-30T01:30:50.614+00:00",
    "ended_offset_seconds": 21.3,
    "errors": {
      "readings_failed": 4,
      "status_reads_failed": 4,
      "submissions_failed": 0
    },
    "fault": "stall",
    "started_at": "2026-09-30T01:30:40.411+00:00",
    "started_offset_seconds": 11.1
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
  "readings_p50_ms": 24.1,
  "readings_p95_ms": 2122.8,
  "readings_submitted": 36,
  "recorded_at": "2026-09-30T01:31:13+00:00",
  "run_seconds": 31.2,
  "sampled_traces": [
    {
      "accepted_offset_seconds": 11.5,
      "exception_id": "exc-defb00d7-af08-5c07-8b25-229539cec338",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/de6c6eec3a001d01694413edeae78416",
      "state": "FAILED",
      "trace_id": "de6c6eec3a001d01694413edeae78416",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 12.4,
      "exception_id": "exc-a639f5fb-7d69-5ed4-853c-97edd547a4c0",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/5cc5649ebe7957457a7b09547a453617",
      "state": "FAILED",
      "trace_id": "5cc5649ebe7957457a7b09547a453617",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 12.7,
      "exception_id": "exc-0bc2a06e-3ce0-5903-8f3c-acd39d5b884e",
      "failure_reason": "model_provider_terminal_failure",
      "jaeger_url": "http://localhost:16686/trace/7ee66788f9feb8a823e4894c238b8753",
      "state": "FAILED",
      "trace_id": "7ee66788f9feb8a823e4894c238b8753",
      "window": "inside"
    },
    {
      "accepted_offset_seconds": 2.0,
      "exception_id": "exc-2b756707-c68d-50ff-958a-794d453c09cd",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/fb1890a0aac6e22c89de0be200a72272",
      "state": "COMPLETED",
      "trace_id": "fb1890a0aac6e22c89de0be200a72272",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 2.0,
      "exception_id": "exc-043a8c4d-7244-5fe1-aec3-660af72e96f9",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/d5bbd8d0dbe3117c8a1d217e861d772c",
      "state": "COMPLETED",
      "trace_id": "d5bbd8d0dbe3117c8a1d217e861d772c",
      "window": "outside"
    },
    {
      "accepted_offset_seconds": 5.3,
      "exception_id": "exc-854bf935-06f1-55d3-b794-01aea6003494",
      "failure_reason": null,
      "jaeger_url": "http://localhost:16686/trace/5a1f0f34015dc193b1533ff3dee4432b",
      "state": "COMPLETED",
      "trace_id": "5a1f0f34015dc193b1533ff3dee4432b",
      "window": "outside"
    }
  ],
  "schema": "coldline-topology-run/1",
  "status_p50_ms": 5.1,
  "status_p95_ms": 1031.3,
  "status_reads": {
    "count": 65,
    "failed": 4
  },
  "submissions": {
    "count": 36,
    "failed": 0
  },
  "throughput_per_second": 1.15
}
```

How the run itself behaved differently. The failure window sat in the same place (+11.1 s to
+21.3 s) and cost the same four readings, but this time it also cost four status reads:
`status_reads_failed: 4`, which were 0 in the split profile. The whole polling side slowed
down with it — only 65 status reads completed in this run against 275 in the split run, and
`status_p50_ms` barely moved (5.1 ms against 4.4 ms) while `status_p95_ms` went from 7.6 ms
to 1031.3 ms, which is the poller's 1 s read timeout. The run settled slightly faster in wall
clock (31.2 s against 32.4 s) with two fewer readings submitted (36 against 38), because the
load step only sends its next reading when the previous response comes back. The stack came
back on its own: the fault was lifted at +21.3 s, the readings accepted after it all reached
`COMPLETED`, and `poe topology-run` finished and wrote the summary without any intervention
from me.

I kept the first run of each profile. Neither run was interrupted, I changed no shell setting
and no host-port override between them, and `poe ready` reported ready before each one, so
both summaries describe the same experiment with the topology as the only difference.

## Comparison

One paragraph per dimension, each naming the figures from both summaries and the trace it
rests on. Latency: `readings_p95_ms` and `status_p95_ms` side by side. Throughput:
`throughput_per_second` side by side. Blast radius: the errors inside each failure window and
which kind they were (failed submissions, failed status reads, readings that ended `FAILED`).
Then the trace pair: which service names appear in each, where the accept span ends and where
`coldline.process_exception` and `model_provider.summarize` begin, and what the failure did to
the summarize span. Close with one sentence on what these two runs cannot show.

**Latency.** Reading submissions cost the same in both topologies: `readings_p95_ms` 2096.5
(split) against 2122.8 (single), a 1.3 % difference, with `readings_p50_ms` 23.6 against
24.1. Status reads did not: `status_p95_ms` 7.6 (split) against 1031.3 (single), while
`status_p50_ms` barely moved (4.4 against 5.1). The single profile's 1031.3 ms is the
poller's 1 s read timeout, so its tail is not a slow read, it is a read that never came
back inside the second. The trace pair explains where that second went: in
`de6c6eec3a001d01694413edeae78416` the `model_provider.summarize` span runs 2504.0 ms
inside the `coldline-single` process — the same process uvicorn answers status reads
from — while in `fe879f670abcbc12fce6dfeccc98d3c2` the equivalent 2510.2 ms span belongs
to `coldline-worker`, a different container from the one serving reads. Dispatcher-facing
median latency is the same in both; only the failure-window tail on status reads differs,
and it differs in the split profile's favour.

**Throughput.** `throughput_per_second` was 1.17 (split) against 1.15 (single): 34 of 38
readings completed in 32.4 s against 32 of 36 in 31.2 s, with exactly 4 readings `FAILED`
in each. That gap is under 2 % and the submitted counts differ by two readings, which the
load step's own closed loop can produce on its own — it sends the next reading only when
the previous response returns, so two fewer submissions lower the numerator without either
topology processing anything more slowly. I read this dimension as no difference these two
runs can support, and no trace is needed for it: a single trace shows one reading's
journey, not the run's rate.

**Blast radius.** The failure windows were the same size and in the same place (+11.4 s to
+21.4 s split, +11.1 s to +21.3 s single) and cost the same four readings, but the kinds of
error differ. Split: `readings_failed: 4`, `status_reads_failed: 0`,
`submissions_failed: 0`, total `failure_window_errors: 4`. Single: `readings_failed: 4`,
`status_reads_failed: 4`, `submissions_failed: 0`, total 8. The drop in completed status
reads over the whole run says the same thing more loudly: 275 in the split run against 65
in the single run, for nearly the same number of readings. The trace pair confirms the
mechanism rather than contradicting it: the 2.5 s stalled `model_provider.summarize` span
carries service name `coldline-single` in the single profile and `coldline-worker` in the
split profile, so in one container that blocked thread is the one dispatchers read status
from, and in two containers it is not. Accepting readings survived both: zero failed
submissions either way.

**The trace pair.** `fe879f670abcbc12fce6dfeccc98d3c2` (split, inside window) and
`de6c6eec3a001d01694413edeae78416` (single, inside window), 14 spans each, read in Jaeger.
Structurally they are the same trace. The accept path ends where the work is handed off:
`POST /api/v1/readings` (23.3 ms split, 16.4 ms single, HTTP 202) covers
`postgres.exceptions.get`, `postgres.exceptions.create`, `postgres.exceptions.transition`
and `job_queue.publish`, and closes there. `coldline.process_exception` begins afterwards
— 56.6 ms after the accept span started in the split trace, 22.9 ms in the single one —
and runs 2528.9 ms against 2528.1 ms. Inside it `model_provider.summarize` starts at
+68.6 ms (split) and +27.3 ms (single) and takes 2510.2 ms against 2504.0 ms. In both the
summarize span ends with `otel.status_code: ERROR` and the same exception,
`domain.errors.TerminalProviderError: provider emulator fault: stall held the call for
2.5 s and then failed` — no retry span, no worker timeout, one terminal failure followed by
a final `postgres.exceptions.transition` to `FAILED`. So the two traces differ only in
their service names, `coldline-api` plus `coldline-worker` against `coldline-single`, and
that is exactly what the pair shows: per reading the failure behaves identically, and the
topology decides only whose thread is held while it does.

**What these two runs cannot show.** Two 30-second runs on one laptop, one sample each, in
a fixed order, cannot separate a real latency difference from host noise or a cold
container — the `readings_p95_ms` tail of about 2.1 s appears in both profiles against a
p50 of 24 ms, so I cannot attribute it to either topology — and they say nothing about
behaviour across hosts, under production traffic or over a longer failure, and nothing at
all about what either topology costs in money.
