# Coldline Task 3.9 — Optional Task 9: Topology experiment

This checkpoint is the complete, settled Coldline platform from Task 3.7, with one question
added about its shape. Today it runs as two services in two containers: `api` accepts readings
and answers status reads, and `worker` takes each accepted reading from the queue and calls the
model provider for its summary. This Task supplies a second profile that runs both in one
process inside one container, a pinned experiment that drives the same load and the same
provider failure against whichever profile is running, and a record template. You run the
experiment twice, compare the two generated summaries and one pair of traces, and record a
structured conclusion and a recommendation for Dana. This Task is optional and adds no code.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/tripleten-com/ai-system-engineering-curriculum-sprint-3-task-3-9/tree/main)

## Start the system

Prerequisites are Python 3.12, git, and Docker with Compose v2. The supplied bootstrap supports
macOS arm64/x86-64, Windows x86-64, and Linux x86-64/aarch64, and installs pinned uv 0.11.8
under `.tools/bin`. If your computer cannot run the stack locally, use the Codespaces button
above.

On macOS and most Linux distributions the interpreter is `python3`; substitute it wherever these
commands say `python`.

```shell
python infra/scripts/bootstrap.py
./.tools/bin/uv sync --frozen
./.tools/bin/uv run --frozen poe preflight
./.tools/bin/uv run --frozen poe start
./.tools/bin/uv run --frozen poe ready
```

PowerShell and POSIX wrappers are available under `infra/scripts/`. After uv is on `PATH`, the
shorter `uv run --frozen poe <task>` form works.

| Service | Local URL | Purpose |
|---|---|---|
| API | `http://localhost:8000` | Submit exception workflows and retrieval queries; `/version` names the build that answers, in either profile |
| Grafana | `http://localhost:3000` | Use the focused diagnostics dashboard |
| Prometheus | `http://localhost:9090` | Query bounded metrics and inspect the deployed alert rule |
| Alertmanager | `http://localhost:9093` | Inspect firing and resolved alerts |
| Jaeger | `http://localhost:16686` | Inspect local traces; this Task's trace pair opens here |
| LocalStack S3/SQS | `http://localhost:4566` | Inspect the emulated object-storage and queue endpoint |

Each of these ports can be overridden by setting the matching `COLDLINE_API_HOST_PORT`,
`COLDLINE_GRAFANA_HOST_PORT`, `COLDLINE_PROMETHEUS_HOST_PORT`, `COLDLINE_ALERTMANAGER_HOST_PORT`,
`COLDLINE_JAEGER_HOST_PORT`, or `COLDLINE_LOCALSTACK_HOST_PORT` environment variable in your shell
environment or a local `.env` file (copy `.env.example`) if a default collides with something
already running on your machine. Keep the override in place for every `poe` command in this
Task: both profiles publish the API on `COLDLINE_API_HOST_PORT`, and `poe topology-run` reads
`COLDLINE_API_HOST_PORT` and `COLDLINE_JAEGER_HOST_PORT` the same way for its requests and its
trace lookups. Changing an override between the two runs makes the two summaries describe
different experiments.

This Task runs as its own Compose project, `coldline-task-3-9`. If an earlier Task's stack is
still running, run `poe stop` in that Task's repository first; otherwise `poe start` here fails
because the published ports are already taken.

PostgreSQL, Redis, worker metrics, and OTLP remain inside the Compose network. Codespaces uses the
same `compose.yaml` and keeps every forwarded port private. Redis keeps running in this Task only
for an earlier checkpoint's own contract test; no composition root reads it anymore.

## Command path

For this Task, run the supplied commands in this order:

```text
poe start
poe ready
poe topology-run
poe start-single
poe ready
poe topology-run
poe start
poe verify
```

The first `poe topology-run` writes `docs/student/topology/split-run.json`; the second, against
the single-process profile, writes `docs/student/topology/single-run.json` and leaves the split
summary in place. Between the second run and `poe verify` sit Steps 3 and 4 of the lesson: the
comparison from the summaries and one pair of traces in Jaeger, then the conclusion and the
recommendation in `submission.yaml` and the record.

| Command | Use |
|---|---|
| `poe start` | The split profile: `api` and `worker` in two containers. It also removes a running `single` container, so it replaces the single-process profile |
| `poe start-single` | The single-process profile: one `single` container from the api image running the API routes and the worker loop on one event loop, from `compose.single.yaml` over `compose.yaml`. It removes the running `api` and `worker` containers first |
| `poe ready` | Wait for the running profile to be ready; it accepts either profile's worker loop |
| `poe topology-run` | The experiment against whichever profile is running: the pinned load step for 30 s, every accepted reading polled to a terminal state, the supplied provider failure applied at 10 s and lifted at 20 s, a few traces sampled from Jaeger, and `docs/student/topology/<profile>-run.json` written with a generator marker and a content digest. No options |
| `poe answers` | The static half of this Task's own check: the answer sheet's format, the topology record's template markers, and the diff from your merge base against the four permitted files |
| `poe topology-checks` | The assessed checks: both summaries are present, name their profile, and carry the digest the run wrote; your recorded figures and trace ids match them field for field; the comparison and the recommendation use the allowed values |
| `poe topology-contract` | `poe answers` and `poe topology-checks` together; the check `poe verify` runs for this Task. It does not rerun the experiment |
| `poe verify` | The public student verification path: it starts the split profile, ingests the corpus, runs `poe topology-contract`, then the smoke tests, the end-to-end workflow, and the supplied student tests |
| `poe queue-contract`, `poe slo-contract`, `poe gate-contract`, `poe runbook-contract` | The inherited Task 3.3 through 3.6 checks over the settled checkpoint; still runnable against the split profile, not part of this Task's verify path |
| `poe load-test` | The pinned Locust profile on its own, as Tasks 1.4 and 1.5 ran it; `poe topology-run` drives the same profile itself |
| `poe contract` | Check interfaces, boundaries, submissions, and repository structure |
| `poe smoke` | Check the initialized running split profile |
| `poe e2e` | Run the external API-to-worker workflow |
| `poe student-tests` | Run the supplied tests under `tests/student/`; this Task permits no additions there |
| `poe dev-failure-lab`, `poe trigger-alert-load`, `poe verify-alert-recovery`, `poe inject-failure`, `poe redrive` | Inherited exercises from Tasks 3.3, 3.4, and 3.6, still runnable against the split profile; not part of this Task |
| `poe restart` | Restart the existing API and worker containers **without rebuilding** (split profile) |
| `poe stop` | Remove containers and the network, keeping named volumes |
| `poe reset` | Remove containers, the network, and local named volumes |

For Task 3.9, `poe verify` starts the split profile (replacing a running single-process profile),
ingests the supplied corpus, runs `poe answers`, runs the topology checks over the two summaries
you committed, then the smoke tests and the end-to-end exception workflow against the split
profile, and the supplied student tests. The inherited Task 3.3 through 3.6 checks are not in
this path; they were qualified against the split checkpoint and remain runnable on their own.

## The two profiles and the experiment

Both profiles run the same code. The split profile is `compose.yaml` as Task 3.7 settled it.
The single-process profile is `compose.single.yaml` layered on top: it parks `api` and `worker`
behind a Compose profile nothing activates and adds `single`, one container from the api image
whose command is `infra/topology/single_process.py`. That entry serves the API application
object from `api.bootstrap` with uvicorn and runs the worker loop composed by
`worker.bootstrap.compose`, both as tasks on one event loop. The container carries the api and
worker resource bounds added together, answers on the same host port, and takes the network
names `api` and `worker` so Prometheus keeps scraping both jobs from the one process. Its spans
carry one service name, `coldline-single`, where the split profile's carry `coldline-api` and
`coldline-worker`; that is how you tell the two profiles apart in Jaeger.

The provider failure is the emulator's own fault control, `src/adapters/model/faults.py`,
applied and lifted inside the container that runs the worker loop with
`python -m adapters.model.faults`. Its one fault, `stall`, makes every provider call block its
thread for 2.5 s, as a hanging synchronous provider client would, and then fail terminally, so
the reading ends `FAILED`. Which paths that blocked thread reaches is the topology's own
property and the experiment's point: in the split profile it belongs to the worker container
alone, and in the single-process profile it is the thread uvicorn serves from.

`poe topology-run` detects the running profile from `docker compose ps` and refuses to run
against a stack that is not ready or a mix of both profiles. Its summary reports the latency
percentiles of the successful submissions and status reads, the throughput from accepted to
terminal over the run, the failure window with its errors by kind, and a few sampled Jaeger
trace ids labelled inside or outside the window, plus a generator marker and a content digest.
The check recomputes the digest, so a summary edited by hand fails; rerun instead. See
[the contract](docs/student/task-3-9-contract.md) for every field's definition.

## Folder map

```text
repository root/
├── compose.single.yaml  The single-process profile, layered over compose.yaml by poe start-single
├── docs/                Student guidance, public contracts, and fidelity notes
│   ├── contracts/       Machine-readable public contracts
│   ├── fidelity/        Local-runtime boundary notes, including the emulator's fault control
│   ├── architecture/    Supplied vector engine technical profiles, in prose
│   ├── retrieval/       Supplied retrieval pipeline reference
│   └── student/         This Task's contract and topology record, the supplied Task 6 runbook,
│                        and topology/, where poe topology-run writes the two summaries
├── config/              Retrieval configuration, settled and supplied from Sprint 2
├── infra/               Local setup and runtime configuration
│   ├── containers/      The API and worker Dockerfiles, with the build identity arguments
│   ├── topology/        The supplied single-process entry, pinned load step, and experiment runner
│   ├── observability/   Prometheus, Alertmanager, and Grafana configuration
│   ├── release/         The supplied Task 3.1 release manifest, unchanged
│   ├── corpus/          Supplied synthetic corpus, query set, and designated investigation
│   ├── judge/           Supplied cached judge evidence and its provenance record
│   ├── profiles/        Supplied engine and emulator profiles, and their provenance record
│   └── postgres/        Database initialization and the migration baseline stamp
├── loadtest/            Supplied traffic profile (the pinned load step) and provider-latency harness
├── migrations/          Alembic environment, revision template, and revisions
├── src/
│   ├── api/             HTTP application code, the retrieval and document paths, composition
│   ├── worker/          Background application code, including the dead-letter depth poller
│   ├── domain/          Shared domain code, contracts, the failure taxonomy, service and repository contracts
│   ├── ports/           Application interfaces
│   └── adapters/        Technology-specific implementations, including the emulator and its fault control
└── tests/
    ├── unit/            Isolated behavior checks
    ├── benchmark/       Supplied evaluation harness, metrics, and adoption policy
    ├── contract/        Interface, retrieval, and repository checks, and this Task's topology checks
    ├── diagnostics/     Supplied stage inspector
    ├── doubles/         Supplied deterministic test doubles
    ├── failure/         Supplied failure-lab and exercise scripts from Tasks 3.3, 3.4, and 3.6 — not this Task's work
    ├── student/         Supplied student tests; no additions in this Task
    ├── smoke/           Running-platform checks, and the readiness wait both profiles use
    └── e2e/             Supplied workflow tools and checks
```

## Overview

Use the Optional Task 9 lesson (Task 3.9 in this repository) to decide what to do. This README
covers local setup and repository orientation.

1. `README.md` — local setup, commands, and permitted changes.
2. [`docs/student/task-3-9-contract.md`](docs/student/task-3-9-contract.md) — what this Task
   assesses and who assesses it, the four Steps, the commands, every summary field's meaning,
   the mapping from the lesson's Check-list to each check, and the four permitted paths.
3. [`docs/student/task-3-9-topology-record.md`](docs/student/task-3-9-topology-record.md) — the
   record template, one section per profile and one for the comparison; replace every marker
   with your own evidence.
4. [`compose.single.yaml`](compose.single.yaml) and
   [`infra/topology/single_process.py`](infra/topology/single_process.py) — the single-process
   profile; read them to see exactly what differs from the split profile.
5. [`docs/fidelity/ModelProvider.md`](docs/fidelity/ModelProvider.md) — what the emulator's
   fault control does and does not emulate.

The application source lives in five flat packages:

| Package | Responsibility |
|---|---|
| `api` | HTTP delivery, API use cases, the retrieval workflow, versioned routes, configuration, and composition |
| `worker` | Background processing, retries, the dead-letter depth poller, configuration, and composition |
| `domain` | Provider-neutral contracts, state rules, identity, redaction, embedding, chunking, fusion, access constraints, failure classification, service and repository contracts |
| `ports` | Exactly five visible application interfaces |
| `adapters` | PostgreSQL, pgvector retrieval, LocalStack SQS/DLQ, S3-compatible object storage, deterministic model with its fault control, the resilient model-provider wrapper, logs, traces |

`src/api/bootstrap.py` and `src/worker/bootstrap.py` compose each process from its settings and
adapters; the single-process entry reuses both compositions unchanged. Process settings live in
`src/api/config.py` and `src/worker/config.py`.

## The five ports

Find the available interfaces in `src/ports/`. A port describes an application capability; an
adapter provides it using a concrete technology.

| Port | General responsibility |
|---|---|
| `ModelProvider` | Call an AI model service |
| `Retriever` | Look up relevant context or documents |
| `ObjectStore` | Store large binary objects or files |
| `JobQueue` | Publish and consume background work |
| `SecretProvider` | Read API keys and credentials |

LocalStack SQS, with a bound dead-letter queue, still carries `JobQueue`, unchanged from Task 3.3,
in both profiles. See [JobQueue fidelity](docs/fidelity/JobQueue.md) for what it does and does
not prove.

## Test levels

| Level | Requires Compose | Main question |
|---|---:|---|
| Unit | No | Does one responsibility behave correctly, including failures? |
| Contract | Some | Do interfaces, schemas, paths, and dependency rules stay compatible? |
| Smoke | Yes | Did the complete local platform initialize and become observable? |
| E2E | Yes | Can an external client complete the supplied workflow? |

Contract checks marked `runtime` need the running stack, and checks marked `assessed` read your
work. `poe contract` skips both; `poe topology-checks` runs this Task's own module, whose five
static checks read the two summaries and the answer sheet and whose one runtime check asks the
running profile's emulator that no fault is left applied. A fresh Task 3.9 checkout fails the
five static checks, because the summaries and the answers are this Task's work; the runtime
check passes against either profile as `poe start` or `poe start-single` brings it up.

## Submission checks

Run `poe verify` locally before opening your student pull request. Public GitHub CI repeats
the student checks, running `poe answers` first so a boundary violation fails fast, then
`poe start`, `poe ingest`, and `poe verify`. The three `split_effect` values in
`answers.comparison` and the `decision` in `answers.recommendation` are compared with a
protected answer key after you submit on the platform; the public checks confirm their format
and their allowed values only. Follow the Task lesson's submission policy: this Task is optional
and gates nothing.

## Task boundary

Task 3.9 asks you to run the supplied experiment against both profiles, fill the answer sheet
from the two summaries, and complete the topology record. The only student-editable paths are:

- `docs/student/task-3-9-topology-record.md`
- `submission.yaml`
- `docs/student/topology/split-run.json` and `docs/student/topology/single-run.json`, written by
  `poe topology-run` only

Change nothing about either topology. Keep `compose.yaml`, `compose.single.yaml`, everything
under `infra/topology/`, the load profile under `loadtest/`, the emulator and its fault control
under `src/adapters/model/`, the worker composition, the transport adapters, every test file,
and both workflows exactly as supplied. Never edit a summary: the check recomputes its digest
and reports an edited one; a figure you disagree with is a reason to rerun. The public check
compares the diff from your merge base against the four permitted files and reports any other
change as a boundary violation.

### Student walkthrough

See **Optional Task 9: Topology experiment** in your course platform for the full walkthrough.
In outline: read `docs/student/task-3-9-contract.md`, start the split profile and run
`poe topology-run`, start the single-process profile and run it again, copy the five fields of
each summary into `answers.runs`, open one inside-window trace from each summary in Jaeger and
record the pair, fill the comparison and the recommendation, complete the record, return to the
split profile with `poe start`, check `git diff --stat` shows only the four permitted files, run
`poe verify`, open your pull request, and submit on the platform.

## Operational limits

This local system does not authenticate users, terminate TLS, or manage production secrets.
The Compose PostgreSQL password and the LocalStack access keys are local-only non-secret
credentials. Never place real credentials, personal data, or production records in this
repository.

Alertmanager here is configured with a "default" receiver that has no notification integration:
alerts are queryable through its own API but never sent anywhere real. Never add a webhook, email,
Slack, or paid integration; Sprints 1-4 are emulator-only and never call a hosted endpoint. The
provider failure is applied to the deterministic emulator by the supplied run; nothing external
is called, and no paid cloud resources or real AI keys are involved.

Two 30-second runs on one laptop are two samples: latency and throughput move with whatever else
the host was doing and with a cold container, and the check compares your answers with your own
summaries, not with a number it expects. The single-process profile shows what one process on
one host does when its provider stalls; it makes no claim about how two services or one behave
across hosts, under production traffic, or in cost. See
[ModelProvider fidelity](docs/fidelity/ModelProvider.md) for what the fault control does not
emulate.

Named volumes preserve local PostgreSQL, Redis, Prometheus, Alertmanager, Grafana, and Jaeger state
across `poe stop`, and Jaeger keeps its traces across a profile switch, which is why both traces
of your pair are there. LocalStack object and queue contents are deliberately not persisted; the
initializer re-uploads the supplied corpus artifacts and re-provisions the queue on every start.
The `poe reset` command deletes the named volumes. This topology makes no backup, replication,
high-availability, disaster-recovery, capacity, latency-SLO, or availability claim beyond the one
alert Task 3.4 configures, the one CI gate Task 3.5 wires to it, and the one bounded recovery
Task 3.6's failure lab demonstrates.

See [JobQueue fidelity](docs/fidelity/JobQueue.md),
[ModelProvider fidelity](docs/fidelity/ModelProvider.md),
[ObjectStore fidelity](docs/fidelity/ObjectStore.md), and
[Retriever fidelity](docs/fidelity/Retriever.md) for the active adapter boundaries. The
[local runtime evidence](docs/fidelity/local-runtime.md) records the current measurement and its
qualification limits.
