"""Coldline.

===================

File:              tests/contract/test_topology_contract.py
Component:         Contract tests — Topology experiment
Purpose:           Check the two generated run summaries and the answers recorded from them.
Interacts With:    docs/student/topology/*.json, submission.yaml, the running profile
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Generated evidence, field-for-field comparison, enumerated conclusions
Tools:             Python 3.12, pytest, Docker Compose

Every check here reads the two summaries `poe topology-run` wrote, the answer sheet, or the
running stack. None of them reruns the experiment and none reads the topology record: the
record is the defense material, and these are what the generated evidence and the answers
have to show on their own. The one check marked `runtime` needs a running profile; the rest
are static. `poe contract` skips this whole module because it is marked `assessed`;
`poe topology-checks`, `poe topology-contract`, and `poe verify` run it.
"""

from typing import Any

import pytest

from tests.contract import topology_contract as topology

pytestmark = [pytest.mark.assessed]


@pytest.fixture(scope="module")
def answers() -> dict[str, Any]:
    """Load the recorded answers once."""
    return topology.load_answers()


@pytest.fixture(scope="module")
def summaries() -> dict[str, dict[str, Any] | None]:
    """Load both summaries once, as written."""
    return {profile: topology.load_summary(profile) for profile in topology.PROFILES}


def test_both_summaries_exist_name_their_profile_and_carry_a_valid_digest(
    summaries: dict[str, dict[str, Any] | None],
) -> None:
    """Both summaries are present, name their profile, and are exactly as the run wrote them."""
    problems: list[str] = []
    for profile in topology.PROFILES:
        problems.extend(topology.summary_problems(summaries[profile], profile))
    assert problems == [], "\n".join(problems)


def test_recorded_run_figures_match_their_summaries_field_for_field(
    answers: dict[str, Any], summaries: dict[str, dict[str, Any] | None]
) -> None:
    """answers.runs.<profile> repeats its summary's four figures as written and one sampled id."""
    runs = topology.mapping(answers, "runs")
    mismatches: list[str] = []
    for profile in topology.PROFILES:
        summary = summaries[profile]
        assert summary is not None, (
            f"docs/student/topology/{profile}-run.json is missing; run `poe topology-run` "
            f"against the {profile} profile"
        )
        recorded = topology.mapping(runs, profile)
        for field_name in topology.RUN_FIELDS:
            if recorded.get(field_name) != summary.get(field_name):
                mismatches.append(
                    f"answers.runs.{profile}.{field_name} records {recorded.get(field_name)!r}; "
                    f"the summary says {summary.get(field_name)!r}"
                )
        trace_id = recorded.get("sampled_trace_id")
        if trace_id not in topology.sampled_trace_ids(summary):
            mismatches.append(
                f"answers.runs.{profile}.sampled_trace_id {trace_id!r} is not one of the ids "
                f"in the {profile} summary's sampled trace list"
            )
    assert mismatches == [], "\n".join(mismatches)


def test_trace_pair_names_one_sampled_trace_id_from_each_summary_and_a_note(
    answers: dict[str, Any], summaries: dict[str, dict[str, Any] | None]
) -> None:
    """answers.trace_pair holds one sampled id per profile and says what the pair shows."""
    pair = topology.mapping(answers, "trace_pair")
    problems: list[str] = []
    for profile in topology.PROFILES:
        summary = summaries[profile]
        recorded = pair.get(f"{profile}_trace_id")
        if summary is None:
            problems.append(f"the {profile} summary is missing, so no trace can come from it")
        elif recorded not in topology.sampled_trace_ids(summary):
            problems.append(
                f"answers.trace_pair.{profile}_trace_id {recorded!r} is not one of the ids in "
                f"the {profile} summary's sampled trace list"
            )
    note = pair.get("note")
    if not isinstance(note, str) or not note.strip():
        problems.append("answers.trace_pair.note must say what the two traces show")
    assert problems == [], "\n".join(problems)


def test_comparison_holds_the_three_dimensions_with_allowed_values_and_notes(
    answers: dict[str, Any],
) -> None:
    """Latency, throughput, and blast radius each carry a split_effect, evidence, and note."""
    comparison = topology.mapping(answers, "comparison")
    problems: list[str] = []
    for dimension in topology.DIMENSIONS:
        entry = topology.mapping(comparison, dimension)
        if entry.get("split_effect") not in topology.SPLIT_EFFECTS:
            problems.append(
                f"answers.comparison.{dimension}.split_effect must be one of "
                f"{', '.join(topology.SPLIT_EFFECTS)}"
            )
        if entry.get("evidence") not in topology.EVIDENCE:
            problems.append(
                f"answers.comparison.{dimension}.evidence must be one of "
                f"{', '.join(topology.EVIDENCE)}"
            )
        note = entry.get("note")
        if not isinstance(note, str) or not note.strip():
            problems.append(f"answers.comparison.{dimension}.note must name its figures")
    assert problems == [], "\n".join(problems)


def test_recommendation_decision_is_an_allowed_value_with_a_note(
    answers: dict[str, Any],
) -> None:
    """The recommendation is one of the three decisions and carries Dana's note."""
    recommendation = topology.mapping(answers, "recommendation")
    assert recommendation.get("decision") in topology.DECISIONS, (
        f"answers.recommendation.decision must be one of {', '.join(topology.DECISIONS)}"
    )
    note = recommendation.get("note")
    assert isinstance(note, str) and note.strip(), (
        "answers.recommendation.note must state what two services gain, what they cost, "
        "which way you would go, and one limit of what two local runs prove"
    )


@pytest.mark.runtime
def test_supplied_fault_control_reports_no_active_fault_in_the_running_profile() -> None:
    """Whichever profile is up, its emulator answers the fault control and is not stalled."""
    try:
        profile = topology.running_profile()
    except topology.TopologyCheckError as exc:
        pytest.fail(str(exc))
    assert profile is not None, (
        "neither the split profile (api and worker) nor the single-process profile (single) "
        "is running; start one with `poe start` or `poe start-single`"
    )
    try:
        status = topology.fault_status(profile)
    except topology.TopologyCheckError as exc:
        pytest.fail(str(exc))
    assert status == "none", (
        f"the {profile} profile's provider emulator still has fault {status!r} applied; "
        "an interrupted `poe topology-run` left it behind, and the next run lifts it"
    )
