"""Coldline.

===================

File:              tests/contract/test_submission.py
Component:         Contract tests — Test Submission
Purpose:           Tests for the public answer and path checks for this Task's submission.
Interacts With:    Published interfaces and repository boundaries
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Compatibility, ownership, export safety
Tools:             Python 3.12, pytest
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.contract.submission_validation import (
    SubmissionError,
    _load_one_document,
    main,
    validate_changed_paths,
    validate_submission,
)

ROOT = Path(__file__).parents[2]
SCHEMA = ROOT / "docs/contracts/submission.schema.json"
RECORD = "docs/student/task-3-9-topology-record.md"
SPLIT_TRACE = "1" * 32
SINGLE_TRACE = "2" * 32


def _run(**overrides: Any) -> dict[str, Any]:
    """Return one well-formed run block."""
    entry: dict[str, Any] = {
        "readings_p95_ms": 21.4,
        "status_p95_ms": 6.3,
        "throughput_per_second": 1.31,
        "failure_window_errors": 5,
        "sampled_trace_id": SPLIT_TRACE,
    }
    entry.update(overrides)
    return entry


def _dimension(**overrides: Any) -> dict[str, Any]:
    """Return one well-formed comparison entry."""
    entry: dict[str, Any] = {
        "split_effect": "hurt",
        "evidence": "summaries",
        "note": "Status p95 6.3 ms split against 812.0 ms single; the single run timed out reads.",
    }
    entry.update(overrides)
    return entry


def valid_answers(**overrides: Any) -> dict[str, object]:
    """Return a complete answer sheet in the published shape."""
    answers: dict[str, Any] = {
        "runs": {
            "split": _run(),
            "single": _run(
                readings_p95_ms=2412.7, status_p95_ms=812.0, sampled_trace_id=SINGLE_TRACE
            ),
        },
        "trace_pair": {
            "split_trace_id": SPLIT_TRACE,
            "single_trace_id": SINGLE_TRACE,
            "note": "Both summarize spans stalled; only the single trace's accept span waited too.",
        },
        "comparison": {
            "latency": _dimension(),
            "throughput": _dimension(split_effect="hurt", evidence="both"),
            "blast_radius": _dimension(evidence="traces"),
        },
        "recommendation": {
            "decision": "run_single",
            "note": "Keep two services: dispatchers kept reading statuses while summaries failed.",
        },
    }
    answers.update(overrides)
    return {"answers": answers}


def _task_root(tmp_path: Path, submission_text: str) -> Path:
    """Stage a minimal Task root the public verifier can validate."""
    (tmp_path / "docs/contracts").mkdir(parents=True)
    (tmp_path / "submission.yaml").write_text(submission_text, encoding="utf-8")
    (tmp_path / "submission-sample.yaml").write_text(
        (ROOT / "submission-sample.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "docs/contracts/submission.schema.json").write_text(
        SCHEMA.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def _with_record(root: Path, text: str) -> None:
    """Place a topology record with the given text beside the staged answer sheet."""
    (root / "docs/student").mkdir(parents=True, exist_ok=True)
    (root / RECORD).write_text(text, encoding="utf-8")


def test_a_complete_sheet_is_well_formed(tmp_path: Path) -> None:
    """The public schema accepts a complete sheet without judging its correctness."""
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers()))

    validate_submission(root / "submission.yaml", SCHEMA)


def test_blank_template_fails_with_field_address(tmp_path: Path) -> None:
    """An untouched answer sheet must identify the first incomplete field."""
    root = _task_root(
        tmp_path, (ROOT / "tests/fixtures/submission-template.yaml").read_text(encoding="utf-8")
    )

    with pytest.raises(SubmissionError, match="answers.runs.split.sampled_trace_id"):
        validate_submission(root / "submission.yaml", SCHEMA)


@pytest.mark.parametrize(
    "profile,overrides,message",
    [
        ("split", {"readings_p95_ms": 0}, "split.readings_p95_ms"),
        ("single", {"status_p95_ms": -1.5}, "single.status_p95_ms"),
        ("split", {"throughput_per_second": "fast"}, "split.throughput_per_second"),
        ("single", {"failure_window_errors": 2.5}, "single.failure_window_errors"),
        ("single", {"failure_window_errors": -1}, "single.failure_window_errors"),
        ("split", {"sampled_trace_id": "ABCDEF0123456789"}, "split.sampled_trace_id"),
        ("split", {"sampled_trace_id": "abc123"}, "split.sampled_trace_id"),
    ],
    ids=[
        "zero-p95",
        "negative-p95",
        "prose-throughput",
        "fractional-errors",
        "negative-errors",
        "uppercase-trace",
        "short-trace",
    ],
)
def test_run_figures_outside_the_published_contract_are_rejected(
    tmp_path: Path, profile: str, overrides: dict[str, Any], message: str
) -> None:
    """The public schema must name the run field it rejected, and reject the right ones."""
    runs = dict(valid_answers()["answers"]["runs"])  # type: ignore[index]
    runs[profile] = _run(**{**runs[profile], **overrides})
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(runs=runs)))

    with pytest.raises(SubmissionError, match=message):
        validate_submission(root / "submission.yaml", SCHEMA)


@pytest.mark.parametrize(
    "dimension,overrides,message",
    [
        ("latency", {"split_effect": "better"}, "latency.split_effect"),
        ("throughput", {"evidence": "dashboard"}, "throughput.evidence"),
        ("blast_radius", {"note": "n" * 301}, "blast_radius.note"),
        ("blast_radius", {"note": ""}, "blast_radius.note"),
    ],
    ids=["effect", "evidence", "long-note", "blank-note"],
)
def test_comparison_entries_outside_the_published_contract_are_rejected(
    tmp_path: Path, dimension: str, overrides: dict[str, Any], message: str
) -> None:
    """A nested enumeration or note cannot hide behind the top-level checks."""
    comparison = dict(valid_answers()["answers"]["comparison"])  # type: ignore[index]
    comparison[dimension] = _dimension(**{**comparison[dimension], **overrides})
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(comparison=comparison)))

    with pytest.raises(SubmissionError, match=message):
        validate_submission(root / "submission.yaml", SCHEMA)


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"decision": "split"}, "recommendation.decision"),
        ({"note": "x" * 601}, "recommendation.note"),
        ({"note": ""}, "recommendation.note"),
    ],
    ids=["unknown-decision", "long-note", "blank-note"],
)
def test_recommendation_outside_the_published_contract_is_rejected(
    tmp_path: Path, overrides: dict[str, Any], message: str
) -> None:
    """The decision is one of three values and the note is bounded and present."""
    recommendation = dict(valid_answers()["answers"]["recommendation"])  # type: ignore[index]
    recommendation.update(overrides)
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(recommendation=recommendation)))

    with pytest.raises(SubmissionError, match=message):
        validate_submission(root / "submission.yaml", SCHEMA)


def test_a_missing_dimension_is_rejected(tmp_path: Path) -> None:
    """All three dimensions are required; two of them is not a comparison."""
    comparison = dict(valid_answers()["answers"]["comparison"])  # type: ignore[index]
    del comparison["blast_radius"]
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(comparison=comparison)))

    with pytest.raises(SubmissionError, match="blast_radius"):
        validate_submission(root / "submission.yaml", SCHEMA)


def test_a_missing_profile_is_rejected(tmp_path: Path) -> None:
    """Both runs are required; one profile's figures are not an experiment."""
    runs = dict(valid_answers()["answers"]["runs"])  # type: ignore[index]
    del runs["single"]
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(runs=runs)))

    with pytest.raises(SubmissionError, match="single"):
        validate_submission(root / "submission.yaml", SCHEMA)


def test_a_trace_pair_outside_the_published_contract_is_rejected(tmp_path: Path) -> None:
    """The pair's ids are trace ids and its note is bounded."""
    pair = dict(valid_answers()["answers"]["trace_pair"])  # type: ignore[index]
    pair["note"] = "x" * 301
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(trace_pair=pair)))

    with pytest.raises(SubmissionError, match="trace_pair.note"):
        validate_submission(root / "submission.yaml", SCHEMA)


@pytest.mark.parametrize(
    "field",
    ["experiment_passed", "instructor_approved", "defense_recording_url", "notes"],
)
def test_no_self_attestation_or_recording_field_is_accepted(tmp_path: Path, field: str) -> None:
    """Reject a self-approval, a pass boolean, or a recording URL."""
    answers = valid_answers()
    mapping = answers["answers"]
    assert isinstance(mapping, dict)
    mapping[field] = True
    root = _task_root(tmp_path, yaml.safe_dump(answers))

    with pytest.raises(SubmissionError, match="Additional properties"):
        validate_submission(root / "submission.yaml", SCHEMA)


def test_exact_sample_copy_is_rejected(tmp_path: Path) -> None:
    """The published sample must not be accepted as a student submission."""
    root = _task_root(tmp_path, (ROOT / "submission-sample.yaml").read_text(encoding="utf-8"))

    with pytest.raises(SubmissionError, match="fictional sample"):
        validate_submission(
            root / "submission.yaml",
            SCHEMA,
            sample_path=root / "submission-sample.yaml",
        )


def test_only_the_four_permitted_paths_may_change() -> None:
    """The answer sheet, the topology record, and the two generated summaries; nothing else."""
    validate_changed_paths(
        [
            "submission.yaml",
            RECORD,
            "docs/student/topology/split-run.json",
            "docs/student/topology/single-run.json",
        ]
    )

    for protected in (
        "compose.yaml",
        "compose.single.yaml",
        "infra/topology/single_process.py",
        "infra/topology/topology_run.py",
        "infra/topology/load_step.py",
        "loadtest/locustfile.py",
        "src/adapters/model/faults.py",
        "src/adapters/model/deterministic.py",
        "src/worker/bootstrap.py",
        "docs/student/topology/notes.json",
        "tests/contract/test_topology_contract.py",
        "tests/student/test_my_topology.py",
        ".github/workflows/task.yml",
        "docs/student/runbook.md",
        "pyproject.toml",
        "README.md",
    ):
        with pytest.raises(SubmissionError, match="protected path changed"):
            validate_changed_paths([protected])


def test_public_entrypoint_reports_an_incomplete_answer_sheet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catch a verifier entrypoint that skips the real submission contract."""
    root = _task_root(
        tmp_path, (ROOT / "tests/fixtures/submission-template.yaml").read_text(encoding="utf-8")
    )
    _with_record(root, (ROOT / RECORD).read_text(encoding="utf-8"))

    assert main(root, changed_paths=[]) == 1
    assert "answers.runs.split.sampled_trace_id is incomplete" in capsys.readouterr().err


def test_public_entrypoint_rejects_an_untouched_topology_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A complete answer sheet with the template record still in place is incomplete."""
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers()))
    _with_record(root, (ROOT / RECORD).read_text(encoding="utf-8"))

    assert main(root, changed_paths=[]) == 1
    assert "template markers" in capsys.readouterr().err


def test_public_entrypoint_accepts_a_completed_sheet_and_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With every marker replaced and the paths inside the boundary, the check passes."""
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers()))
    _with_record(root, "# Task 3.9 topology record\n\n## Step 1\n\nMy own summary.\n")

    assert (
        main(
            root,
            changed_paths=[
                "submission.yaml",
                RECORD,
                "docs/student/topology/split-run.json",
                "docs/student/topology/single-run.json",
            ],
        )
        == 0
    )
    assert "Task 3.9 answer verification passed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "answers: {value: first, value: second}\n",
        "answers: &answer {value: fictional}\n",
        "answers: *missing\n",
        "answers: {<<: {value: fictional}}\n",
        "answers: {value: 2026-09-04}\n",
        "answers: {value: !custom fictional}\n",
        "answers: {1: fictional}\n",
    ],
    ids=["duplicate-key", "anchor", "alias", "merge-key", "date", "custom-tag", "non-string-key"],
)
def test_non_json_yaml_constructs_are_rejected(tmp_path: Path, unsafe_text: str) -> None:
    """Reject restricted syntax before schema validation can mask a parser defect."""
    submission = tmp_path / "submission.yaml"
    submission.write_text(unsafe_text, encoding="utf-8")

    with pytest.raises(SubmissionError, match="restricted YAML"):
        _load_one_document(submission)


def test_multiple_yaml_documents_are_rejected(tmp_path: Path) -> None:
    """A second document cannot supply or replace the answer mapping."""
    submission = tmp_path / "submission.yaml"
    submission.write_text("answers: {}\n---\nanswers: {}\n", encoding="utf-8")

    with pytest.raises(SubmissionError, match="exactly one YAML mapping"):
        _load_one_document(submission)
