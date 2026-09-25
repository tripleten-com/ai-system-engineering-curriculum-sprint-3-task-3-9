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

_Write your evidence here._

## Step 2 - Single-process profile

The `docker compose ps` output showing one `single` container where `api` and `worker` were,
then `docs/student/topology/single-run.json` as written, and anything that differed in how
the run itself behaved: how long it took to settle, and whether the stack came back after the
failure without help. If you reran a profile, say which run you kept and why.

_Write your evidence here._

## Comparison

One paragraph per dimension, each naming the figures from both summaries and the trace it
rests on. Latency: `readings_p95_ms` and `status_p95_ms` side by side. Throughput:
`throughput_per_second` side by side. Blast radius: the errors inside each failure window and
which kind they were (failed submissions, failed status reads, readings that ended `FAILED`).
Then the trace pair: which service names appear in each, where the accept span ends and where
`coldline.process_exception` and `model_provider.summarize` begin, and what the failure did to
the summarize span. Close with one sentence on what these two runs cannot show.

_Write your evidence here._
