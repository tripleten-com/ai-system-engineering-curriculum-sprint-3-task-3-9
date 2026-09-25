"""Coldline.

===================

File:              tests/contract/test_authoring_contract.py
Component:         Repository integrity contract
Purpose:           Verifies required Task repository structure and configuration.
Interacts With:    Repository integrity checks and the complete Task tree
Sprint/Task:       Sprint 3 — Project 3
Concepts:          Dependency direction, configuration ownership, repository integrity
Tools:             Python 3.12, pytest
"""

import re
from pathlib import Path

import pytest

from tests.contract import authoring
from tests.contract.submission_validation import _changed_paths

TASK_ROOT = Path(__file__).resolve().parents[2]
BANNER_PATTERN = re.compile(r"Coldline(?: — Task \d+\.\d+)?\.")
# Task 3.9's pull request changes exactly four files, and grants no directory
# prefix. Keep this in sync with submission_validation.ALLOWED_PATHS and
# ALLOWED_PREFIXES. Both Compose files, the single-process entry, the topology
# runner, the load profile, the emulator's fault controls, and every test and
# workflow file are absent here on purpose: the lesson says nothing about
# either topology changes. The two summaries are generated evidence, permitted
# so they can be committed and checked for an unedited digest.
SUBMISSION_DIFF_ALLOWLIST = frozenset(
    {
        "submission.yaml",
        "docs/student/task-3-9-topology-record.md",
        "docs/student/topology/split-run.json",
        "docs/student/topology/single-run.json",
    }
)
SUBMISSION_DIFF_PREFIXES: tuple[str, ...] = ()
HEADER_FIELDS = (
    "File:",
    "Component:",
    "Purpose:",
    "Interacts With:",
    "Sprint/Task:",
    "Concepts:",
    "Tools:",
)
COMMENTABLE_CONFIGURATION = (
    ".devcontainer/post-create.sh",
    "alembic.ini",
    "compose.single.yaml",
    "config/retrieval-baseline.yaml",
    "config/student/retrieval.yaml",
    "infra/profiles/object-store-fidelity.yaml",
    "infra/profiles/vector-engines.yaml",
    "infra/release/manifest.yaml",
    ".devcontainer/start-stack.sh",
    ".dockerignore",
    ".env.example",
    ".gitattributes",
    ".github/workflows/task.yml",
    ".gitignore",
    "compose.yaml",
    "infra/containers/api.Dockerfile",
    "infra/containers/worker.Dockerfile",
    "infra/observability/alertmanager.yml",
    "infra/observability/alerts.yml",
    "infra/observability/grafana/dashboards/provider.yml",
    "infra/observability/grafana/datasources/datasources.yml",
    "infra/observability/prometheus.yml",
    "infra/postgres/001_opening_checkpoint.sql",
    "infra/postgres/002_retrieval_corpus.sql",
    "infra/postgres/003_idempotency.sql",
    "infra/postgres/004_migration_baseline.sql",
    "infra/scripts/bootstrap.ps1",
    "infra/scripts/bootstrap.sh",
    "infra/scripts/preflight.ps1",
    "infra/scripts/preflight.sh",
    "pyproject.toml",
    "submission-sample.yaml",
    "submission.yaml",
)


def test_current_repository_satisfies_the_integrity_contract() -> None:
    """Fail when a protected repository invariant drifts."""
    assert authoring.main() == 0


@pytest.mark.parametrize(
    "fixture",
    ["infra/corpus/README.md", "infra/judge/README.md", "infra/profiles/README.md"],
)
def test_supplied_fixtures_carry_a_provenance_and_licence_record(fixture: str) -> None:
    """Every supplied fixture must say where it came from and under what terms."""
    record = (TASK_ROOT / fixture).read_text(encoding="utf-8")
    for required in ("Synthetic", "Licence", "Provenance"):
        assert required in record, f"{fixture} does not state {required.lower()}"


def test_python_files_have_the_student_navigation_banner() -> None:
    """Catch a source file that gives students no ownership or purpose context."""
    failures: list[str] = []
    # infra/topology holds this Task's supplied single-process entry, load step, and
    # experiment runner; they carry the same banner as the application source and the tests.
    roots = [
        TASK_ROOT / "src",
        TASK_ROOT / "tests",
        TASK_ROOT / "infra/scripts",
        TASK_ROOT / "infra/topology",
    ]
    for root in roots:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            header = text[:1200]
            missing = [field for field in HEADER_FIELDS if field not in header]
            if not BANNER_PATTERN.search(header):
                missing.insert(0, "Coldline navigation banner")
            if missing:
                failures.append(f"{path.relative_to(TASK_ROOT)}: {', '.join(missing)}")

    assert failures == []


# Scoped to a student submission: it asserts the diff from the merge base stays inside this
# Task's student-editable boundary. A generated export PR necessarily changes more than that,
# so template CI deselects this marker. Student CI and `poe author-verify` still run it.
@pytest.mark.submission_boundary
def test_submission_change_stays_within_the_permitted_diff() -> None:
    """Reject any changed path other than the four this Task permits.

    The diff from the merge base is compared against an allowlist holding the answer sheet,
    the topology record, and the two generated summaries, with no prefix exempted. A change
    to either Compose file, the single-process entry, the topology runner, the load profile,
    the fault controls, a test, a workflow, or any application or configuration file fails
    it, whatever else that change does.
    """
    changed = {
        path for path in _changed_paths(TASK_ROOT) if not path.startswith(SUBMISSION_DIFF_PREFIXES)
    }
    assert changed <= SUBMISSION_DIFF_ALLOWLIST


def test_commentable_configuration_files_explain_their_role() -> None:
    """Catch operational files that provide configuration without context."""
    banner = re.compile(r"(?m)^(?:#|--) Coldline(?: - Task \d+\.\d+)?$")
    missing = []
    for relative in COMMENTABLE_CONFIGURATION:
        text = (TASK_ROOT / relative).read_text(encoding="utf-8")
        if not banner.search(text[:1000]):
            missing.append(relative)

    assert missing == []


def test_released_repository_has_no_unresolved_template_tokens() -> None:
    """A student-facing README must not contain an unresolved placeholder."""
    assert authoring._check_unresolved_template_tokens([TASK_ROOT / "README.md"]) == []


def test_topology_record_template_carries_one_section_per_profile_and_the_comparison() -> None:
    """The supplied record template names both profiles and the comparison, each marked."""
    text = (TASK_ROOT / "docs/student/task-3-9-topology-record.md").read_text(encoding="utf-8")
    for section in ("## Step 1", "## Step 2", "## Comparison"):
        assert section in text, f"the topology record template lacks a {section} section"
    assert text.count("_Write your evidence here._") == 3
