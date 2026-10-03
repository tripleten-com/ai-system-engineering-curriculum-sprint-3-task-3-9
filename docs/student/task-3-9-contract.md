# Task 3.9 — Topology experiment contract

Your repository is the finished Project 3 system. This Task changes nothing about what
Coldline does; it asks whether Coldline should keep running as two services or as one, and
answers with measurements from your own stack. You run the same supplied experiment against
the split profile you run today and against a supplied single-process profile, compare the
two generated summaries and one pair of traces, and record a structured conclusion and a
recommendation for Dana. You write no application code, and you never edit a summary.

## What is assessed, and by whom

| Assessed | By |
|---|---|
| The pull request changes only `submission.yaml`, `docs/student/task-3-9-topology-record.md`, `docs/student/topology/split-run.json`, and `docs/student/topology/single-run.json` | Automated, in this repository (`poe answers`, and `poe verify` repeats it) |
| The answer sheet has the published shape, every enumerated field holds an allowed value, and the topology record has no template marker left | Automated (same command) |
| Both summaries exist, name their profile, were written by `poe topology-run`, and are as it wrote them | Automated, in this repository (`poe topology-checks`) |
| `answers.runs.split` and `answers.runs.single` match their summaries field for field | Automated (same command) |
| `answers.trace_pair` names one sampled trace id from each summary | Automated (same command) |
| `answers.comparison` and `answers.recommendation` hold the allowed values with notes | Automated (same command) |
| The three `split_effect` values and the recommendation's `decision` | Protected automated check, after you submit on the platform |
| Your topology record, your notes, and your recommendation | Your instructor, if the Add-On evidence is referenced at the Project Defense |

## The supplied pieces

| Supplied | Where | What it does |
|---|---|---|
| The split profile | `compose.yaml`, `poe start` | The topology you run today: `api` and `worker` in two containers. `poe start` now also removes a running `single` container, so it replaces the other profile. |
| The single-process profile | `compose.single.yaml`, `infra/topology/single_process.py`, `poe start-single` | One `single` container from the api image that serves the API routes and runs the worker loop on one event loop, with the same PostgreSQL, LocalStack, Jaeger and Prometheus around it. The API answers on the same host port. |
| The pinned load step | `loadtest/locustfile.py`, `infra/topology/load_step.py` | The traffic shape `poe load-test` sends (two users, 1.0 to 1.4 s between submissions, 30 s), fixed so two runs are comparable. |
| The provider failure | `src/adapters/model/faults.py` | The emulator's fault control. Its one fault, `stall`, makes every provider call block its thread for 2.5 s and then fail terminally, so the reading ends `FAILED`. `poe topology-run` applies it 10 s after the load step's first request and lifts it at 20 s. |
| The experiment | `infra/topology/topology_run.py`, `poe topology-run` | Detects the running profile, runs the load step, polls every accepted reading to a terminal state, applies and lifts the failure, samples traces from Jaeger, and writes the summary. |
| The record template | `docs/student/task-3-9-topology-record.md` | One section per profile and one for the comparison. |

## The four Steps

### Step 1 — Run the experiment against the split profile

Start the stack with `poe start`, then `poe ready`, and confirm `docker compose --profile
observability --profile localstack ps` lists separate `api` and `worker` containers. Run
`poe topology-run`. Copy the five fields of `docs/student/topology/split-run.json` into
`answers.runs.split` and paste the summary into Step 1 of the record.

### Step 2 — Run the same experiment against the single-process profile

Run `poe start-single`, then `poe ready`. `docker compose ps` now lists one `single`
container where `api` and `worker` were. Run `poe topology-run` again, with nothing changed.
Copy the five fields of `docs/student/topology/single-run.json` into `answers.runs.single`
and paste the summary into Step 2 of the record.

### Step 3 — Compare the two runs from the summaries and from a pair of traces

Read the two summaries side by side for latency, throughput and blast radius. From each
summary, choose one sampled trace id labelled `inside` the failure window, open both in Jaeger
(`http://localhost:16686/trace/<trace id>`, or the port you overrode), and record the pair in
`answers.trace_pair`. Write the comparison section of the record.

### Step 4 — Record the conclusion and the recommendation

Fill `answers.comparison` for `latency`, `throughput` and `blast_radius` (each a
`split_effect`, an `evidence` source and a note) and `answers.recommendation` (a `decision`
and a note in Dana's terms). The enumerated values are checked against a protected answer key
after you submit.

## Commands

```shell
poe start             # the split profile; also replaces a running single-process profile
poe start-single      # the single-process profile; replaces the running split profile
poe ready             # wait for the running profile to be ready
poe topology-run      # the experiment against whichever profile is running; writes its summary
poe answers           # the static half: answer format, record markers, permitted-path boundary
poe topology-checks   # the assessed checks over the two summaries and the answers
poe topology-contract # both halves together; the check poe verify runs for this Task
poe verify            # the full public path, from the split profile
```

`poe topology-run` takes about a minute per profile: the run's clock starts at the load step's
first request, the load step runs for 30 s from there, the failure window sits between 10 s and
20 s on that clock, and the run then waits for the accepted readings to settle and for Jaeger to
have exported the sampled traces. A slow Locust start on a first run only delays the run; it
never shortens the load or moves the window. It refuses to start against a stack whose
`/health/ready` is not 200, lifts any fault an interrupted run left behind, and never leaves
one applied. Keep any host-port override in place for every command; the runner reads
`COLDLINE_API_HOST_PORT` and `COLDLINE_JAEGER_HOST_PORT` the same way the stack does.

## What the summary reports

Every field below is written by `poe topology-run`, and the check reads it as written:

| Field | Meaning |
|---|---|
| `profile` | `split` or `single`, the profile that was running |
| `compose_services` | The first-party containers that were running: `api` and `worker`, or `single` |
| `readings_p95_ms`, `readings_p50_ms` | Latency of the successful `POST /api/v1/readings` requests over the whole run |
| `status_p95_ms`, `status_p50_ms` | Latency of the successful `GET /api/v1/exceptions/{exception_id}` reads; a read that timed out (1 s) is a failed status read, not a latency |
| `throughput_per_second` | Readings that reached a terminal state, divided by the seconds from the first request to the moment the last reading settled |
| `failure_window` | The fault, when it was applied and lifted (timestamps, and offsets from the load step's first request), and the errors inside it by kind: failed submissions, failed status reads, readings that ended `FAILED` |
| `failure_window_errors` | The three kinds added together |
| `sampled_traces` | A few readings' Jaeger trace ids, each labelled `inside` (its summary attempt met the failure: it ended `FAILED` because of the fault, or reached its terminal state while the window was open) or `outside`, with the reading's state and a Jaeger link |
| `generator`, `digest` | The generator marker and a SHA-256 content digest over the rest of the file |

## What the checks verify

Each row of the lesson's Check-list maps to one check:

| Check-list row | Check | What it looks at |
|---|---|---|
| `docs/student/topology/split-run.json` and `docs/student/topology/single-run.json` exist, name their profile, and are exactly as `poe topology-run` wrote them | `test_both_summaries_exist_name_their_profile_and_carry_a_valid_digest` | Both files parse, carry the generator marker, name the profile their filename names, list the profile's containers (`api` and `worker`, or `single`), report a failure window that started and ended inside the run and at least one labelled sampled trace, and their digest recomputes over their content |
| `answers.runs.split` and `answers.runs.single` match their summaries field for field | `test_recorded_run_figures_match_their_summaries_field_for_field` | `readings_p95_ms`, `status_p95_ms`, `throughput_per_second` and `failure_window_errors` equal the summary's values as written, and `sampled_trace_id` is one of the summary's sampled trace ids |
| `answers.trace_pair` names one sampled trace id from each summary and a non-empty note | `test_trace_pair_names_one_sampled_trace_id_from_each_summary_and_a_note` | Each id is in its own summary's sampled list; the note is present |
| `answers.comparison` holds `latency`, `throughput` and `blast_radius`, each with `split_effect` and `evidence` from the allowed values and a non-empty note | `test_comparison_holds_the_three_dimensions_with_allowed_values_and_notes` (and the schema) | The three entries and their enumerations; the values themselves are compared with the protected answer key after you submit |
| `answers.recommendation.decision` is one of the allowed values and its note is non-empty | `test_recommendation_decision_is_an_allowed_value_with_a_note` (and the schema) | `keep_split`, `run_single` or `not_settled`, with the note; the decision is compared with the protected answer key after you submit |
| The topology record replaces every template marker | `tests/contract/submission_validation.py` (`poe answers`) | `docs/student/task-3-9-topology-record.md` no longer contains `_Write your evidence here._` |
| The pull request modifies only the four permitted files | `tests/contract/submission_validation.py` (`poe answers`) and `test_submission_change_stays_within_the_permitted_diff` | The diff from the merge base with `main` against the four-file allowlist, with no directory prefix exempted |

One more check in the same module is marked `runtime` and assesses nothing of yours:
`test_supplied_fault_control_reports_no_active_fault_in_the_running_profile` asks the running
profile's emulator which fault is active and expects `none`, so a stalled emulator left behind
by an interrupted run is named before the smoke and end-to-end checks meet it. `poe contract`
skips this whole module because it is marked `assessed`; `poe topology-checks`,
`poe topology-contract`, and `poe verify` run it. A fresh checkout fails the five static checks,
because the summaries and the answers are this Task's work.

## Student-editable paths

- `submission.yaml`
- `docs/student/task-3-9-topology-record.md`
- `docs/student/topology/split-run.json`, written by `poe topology-run` only
- `docs/student/topology/single-run.json`, written by `poe topology-run` only

That is the whole list. Both Compose files, `infra/topology/`, the load profile under
`loadtest/`, the emulator and its fault control under `src/adapters/model/`, the worker
composition, every test, and both workflows stay as supplied. A summary you edit by hand
fails the digest check; a figure you disagree with is a reason to rerun, never to retype.
Before you push, run `git status` and `git diff --stat` against your merge base: if anything
besides the four files changed, the public check reports the boundary violation rather than
your work.

## What this local experiment does not prove

Two 30-second runs on one laptop are two samples. Latency and throughput move with whatever
else the host was doing, with a cold container, and with the order you ran the profiles in;
the check compares your answers with your own summaries, not with a number it expects. What
the experiment does settle by construction is where the failure reached: the stall holds the
thread the worker loop runs on, which in the split profile is the worker container's own and
in the single-process profile is the one the API routes share. Say in your record and in
`answers.recommendation.note` what a longer run, a second host, or production traffic would
be needed to show.
