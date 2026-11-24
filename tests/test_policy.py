"""Source-authority policy (EK-004, ADR-0010), on synthetic sources and records."""

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from rdflib.namespace import XSD
from typer.testing import CliRunner

from ek.adapters.base import EmployeeRecord, ReadResult
from ek.cli import app
from ek.config import SourceConfig
from ek.constants import AUDIT_GRAPH, EK, UNTRUSTED_GRAPH
from ek.graph.store import KnowledgeStore
from ek.ingest import assertion_uri, ingest
from ek.policy import (
    PolicyError,
    in_force,
    load_policy,
    version_in_force,
)
from ek.reconcile import build_report
from ek.review import review

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SOURCES = {"hr", "directory", "third"}
TODAY = date(2026, 6, 1)

HEADER = 'version = "v1"\neffective_from = 2026-01-01\n'
DEPARTMENT = """
[[properties]]
property = "department"
authoritative = ["hr"]
secondary = ["directory"]
conflict_rule = "prefer-authoritative"
freshness_days = 30
required = true
reviewer_roles = ["hr-reviewer"]
"""


def write(tmp_path, text, name="policy.toml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def policy(tmp_path, rows=DEPARTMENT, header=HEADER):
    return load_policy(write(tmp_path, header + rows), SOURCES)


def load(store, source, day=1, **records):
    """records: employee_id -> department raw value."""
    cfg = SourceConfig(
        source,
        "excel",
        issuer="example-hr",
        mapping_version="1",
        mapping={"employee_id": "id"},
    )
    rows = [
        EmployeeRecord(emp, {"department": dept}, f"{source}.xlsx#People!{n}")
        for n, (emp, dept) in enumerate(records.items(), start=2)
    ]
    result = ReadResult(f"{source}.xlsx", "a" * 64, rows)
    ingest(store, cfg, result, datetime(2026, 1, day, tzinfo=UTC))


def dept(source, value, emp="E1"):
    return assertion_uri(source, emp, EK.department, XSD.string, value)


def act(store, a, action, **kw):
    return review(store, a, action, reviewer="r", reason="Checked", **kw)


def conflict(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", E1="Eng")
    load(store, "directory", E1="Product")
    return store


# -- loader -------------------------------------------------------------------


def test_valid_policy_loads(tmp_path):
    p = policy(tmp_path)
    assert (p.version, p.effective_from) == ("v1", date(2026, 1, 1))
    row = p.properties[EK.department]
    assert row.authoritative == ("hr",) and row.secondary == ("directory",)
    assert (row.freshness_days, row.required) == (30, True)
    assert row.reviewer_roles == ("hr-reviewer",)


def test_missing_file_is_no_policy(tmp_path):
    assert load_policy(tmp_path / "absent.toml", SOURCES) is None


def test_defaults(tmp_path):
    row = policy(
        tmp_path,
        '[[properties]]\nproperty = "location"\nauthoritative = []\n'
        'conflict_rule = "manual"\n',
    ).properties[EK.location]
    assert (row.secondary, row.freshness_days, row.required) == ((), None, False)
    assert row.reviewer_roles == ()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("version = ", "invalid TOML"),
        (HEADER + "owner = 'x'\n", "unknown top-level keys"),
        ('version = " "\neffective_from = 2026-01-01\n', "'version'"),
        ('version = "v1"\n', "'effective_from'"),
        ('version = "v1"\neffective_from = "2026-01-01"\n', "'effective_from'"),
        ('version = "v1"\neffective_from = 2026-01-01T00:00:00Z\n', "'effective_from'"),
        (HEADER + "properties = 3\n", "array of tables"),
    ],
)
def test_file_level_errors(tmp_path, text, message):
    with pytest.raises(PolicyError, match=message):
        load_policy(write(tmp_path, text), SOURCES)


def row(**overrides):
    fields = {
        "property": '"department"',
        "authoritative": '["hr"]',
        "conflict_rule": '"prefer-authoritative"',
    }
    fields.update(overrides)
    body = "".join(f"{k} = {v}\n" for k, v in fields.items() if v is not None)
    return "[[properties]]\n" + body


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (row(review_required="false"), "unknown keys"),  # review is never waived
        (row(trusted="true"), "unknown keys"),
        (row(property='"salary"'), "unknown property"),
        (row(property=None), "unknown property"),
        (row() + row(), "duplicate property"),
        (row(authoritative=None), "'authoritative' is required"),
        (row(authoritative='["nope"]'), "unknown sources"),
        (row(secondary='["nope"]'), "unknown sources"),
        (row(secondary='["hr"]'), "both authoritative and secondary"),
        (row(authoritative='"hr"'), "list of non-blank strings"),
        (row(reviewer_roles='[" "]'), "list of non-blank strings"),
        (row(conflict_rule='"newest"'), "'conflict_rule'"),
        (row(conflict_rule=None), "'conflict_rule'"),
        (row(authoritative="[]"), "needs an authoritative source"),
        (row(freshness_days="0"), "positive integer"),
        (row(freshness_days="-1"), "positive integer"),
        (row(freshness_days='"30"'), "positive integer"),
        (row(freshness_days="true"), "positive integer"),
        (row(freshness_days="1.5"), "positive integer"),
        (row(required='"yes"'), "'required'"),
    ],
)
def test_row_errors(tmp_path, rows, message):
    with pytest.raises(PolicyError, match=message):
        policy(tmp_path, rows)


def test_unreadable_file_is_an_error(tmp_path):
    (tmp_path / "dir.toml").mkdir()
    with pytest.raises(PolicyError, match="cannot be read"):
        load_policy(tmp_path / "dir.toml", SOURCES)


def test_future_policy_is_not_in_force(tmp_path):
    p = policy(tmp_path, header='version = "v2"\neffective_from = 2026-07-01\n')
    assert not in_force(p, TODAY) and version_in_force(p, TODAY) == "none"
    assert in_force(p, date(2026, 7, 1)) and version_in_force(p, date(2026, 7, 1))
    assert version_in_force(None, TODAY) == "none"


def test_example_policy_loads_against_example_sources():
    from ek.config import load_sources

    sources = set(load_sources(EXAMPLES / "sources.toml"))
    assert load_policy(EXAMPLES / "policy.toml", sources).version == "example-1"


# -- evaluation, on real report output -------------------------------------------


def outcome(store, p, today=TODAY):
    [item] = build_report(store, p, today)["discrepancies"]
    return item["policy"]


def test_no_policy_or_no_row_is_no_policy(tmp_path):
    store = conflict(tmp_path)
    assert outcome(store, None)["outcome"] == "no-policy"
    other = policy(
        tmp_path,
        '[[properties]]\nproperty = "location"\nauthoritative = []\n'
        'conflict_rule = "manual"\n',
    )
    assert outcome(store, other)["outcome"] == "no-policy"
    future = policy(tmp_path, header='version = "v2"\neffective_from = 2027-01-01\n')
    assert outcome(store, future)["outcome"] == "no-policy"


def test_manual_rule_recommends_nothing(tmp_path):
    p = policy(tmp_path, row(conflict_rule='"manual"', reviewer_roles='["x"]'))
    result = outcome(conflict(tmp_path), p)
    assert result["outcome"] == "manual" and result["recommended"] == []
    assert result["reviewer_roles"] == ["x"]


def test_single_authoritative_value_is_recommended(tmp_path):
    result = outcome(conflict(tmp_path), policy(tmp_path))
    assert result["outcome"] == "recommend"
    assert result["recommended"] == [str(dept("hr", "Eng"))]
    assert result["reviewer_roles"] == ["hr-reviewer"]
    assert "Eng" not in result["rationale"]  # rationales name sources, not values


def test_authoritative_sources_that_disagree_are_unresolved(tmp_path):
    store = conflict(tmp_path)
    load(store, "third", E1="Ops")
    p = policy(tmp_path, row(authoritative='["hr", "third"]'))
    result = outcome(store, p)
    assert result["outcome"] == "unresolved" and result["recommended"] == []


def test_no_authoritative_fact_is_unresolved(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "directory", E1="Product")
    load(store, "third", E1="Ops")
    assert outcome(store, policy(tmp_path))["outcome"] == "unresolved"


@pytest.mark.parametrize("set_aside", ["reject", "supersede"])
def test_rejected_or_superseded_authoritative_fact_is_ignored(tmp_path, set_aside):
    store = conflict(tmp_path)
    old = dept("hr", "Eng")
    if set_aside == "supersede":
        act(store, old, "accept")
    act(store, old, set_aside)
    assert outcome(store, policy(tmp_path))["outcome"] == "unresolved"
    load(store, "hr", day=2, E1="Ops")  # a new HR value, still a candidate
    result = outcome(store, policy(tmp_path))
    assert result["recommended"] == [str(dept("hr", "Ops"))]


def test_value_gone_from_latest_run_still_counts_but_is_flagged(tmp_path):
    store = conflict(tmp_path)
    load(store, "hr", day=2, E2="Ops")  # E1's HR value is no longer observed
    result = outcome(store, policy(tmp_path))
    assert result["outcome"] == "recommend"
    assert "not in the latest run" in result["rationale"]


# -- invariants (regression) --------------------------------------------------------


def test_evaluation_changes_nothing(tmp_path):
    store = conflict(tmp_path)
    before = len(store.dataset)
    report = build_report(store, policy(tmp_path), TODAY)
    assert report["policy"] == {"version": "v1", "in_force": True}
    assert len(store.dataset) == before
    assert store.check_projection() == []
    for _, a, _ in store.assertions():
        assert store.state(a) == EK.Candidate
        assert store.graph_of(a) == UNTRUSTED_GRAPH
    assert store.events() == []


def test_conflict_without_policy_stays_unresolved_and_untrusted(tmp_path):
    store = conflict(tmp_path)
    report = build_report(store)
    assert report["policy"] is None
    [item] = report["discrepancies"]
    assert item["policy"]["outcome"] == "no-policy"
    assert {f["status"] for f in item["facts"]} == {"Candidate"}


# -- review records the policy version ---------------------------------------------


def test_review_records_policy_version(tmp_path):
    store = conflict(tmp_path)
    event = act(store, dept("hr", "Eng"), "accept", policy_version="v1").event
    audit = store.dataset.graph(AUDIT_GRAPH)
    assert str(audit.value(event, EK.policyVersion)) == "v1"
    event = act(store, dept("directory", "Product"), "reject").event
    assert str(audit.value(event, EK.policyVersion)) == "none"


# -- CLI ----------------------------------------------------------------------------


def cli_store(tmp_path, monkeypatch):
    path = tmp_path / "s.trig"
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(path))
    store = conflict(tmp_path)
    store.save()
    sources = tmp_path / "sources.toml"
    sources.write_text(
        "".join(
            f'[[sources]]\nid = "{s}"\nkind = "jira"\nenabled = false\n'
            "allowed_projects = []\n"
            for s in sorted(SOURCES)
        ),
        encoding="utf-8",
    )
    return path, ["--config", str(sources)]


WHO = ["--reviewer", "r", "--reason", "Checked"]


def audit_versions(path):
    store = KnowledgeStore(path)
    audit = store.dataset.graph(AUDIT_GRAPH)
    return [str(audit.value(e, EK.policyVersion)) for e in store.events()]


def test_cli_review_records_policy_in_force(tmp_path, monkeypatch):
    path, config = cli_store(tmp_path, monkeypatch)
    pol = write(tmp_path, HEADER + DEPARTMENT)
    run = CliRunner().invoke
    ok = run(
        app,
        [
            "review",
            "accept",
            str(dept("hr", "Eng")),
            *WHO,
            "--policy",
            str(pol),
            *config,
        ],
    )
    assert ok.exit_code == 0, ok.output
    assert "(policy v1)" in ok.output
    # No file at the default path (the test's cwd): no policy, recorded as "none".
    ok = run(app, ["review", "reject", str(dept("directory", "Product")), *WHO])
    assert ok.exit_code == 0, ok.output
    assert "No authority policy loaded" in ok.output
    assert audit_versions(path) == ["v1", "none"]


def test_cli_future_policy_records_none(tmp_path, monkeypatch):
    path, config = cli_store(tmp_path, monkeypatch)
    pol = write(tmp_path, 'version = "v9"\neffective_from = 2999-01-01\n')
    result = CliRunner().invoke(
        app,
        [
            "review",
            "accept",
            str(dept("hr", "Eng")),
            *WHO,
            "--policy",
            str(pol),
            *config,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "not in force" in result.output
    assert audit_versions(path) == ["none"]


@pytest.mark.parametrize("command", ["review", "report", "report-json"])
def test_cli_invalid_policy_exits_and_writes_nothing(tmp_path, monkeypatch, command):
    path, config = cli_store(tmp_path, monkeypatch)
    before = path.read_bytes()
    pol = write(tmp_path, HEADER + row(trusted="true"))
    args = {
        "review": ["review", "accept", str(dept("hr", "Eng")), *WHO],
        "report": ["report"],
        "report-json": ["report-json", "--output", str(tmp_path / "r.json")],
    }[command]
    result = CliRunner().invoke(app, [*args, "--policy", str(pol), *config])
    assert result.exit_code == 1 and "unknown keys" in result.output
    assert path.read_bytes() == before
    assert not (tmp_path / "r.json").exists()


def test_cli_policy_without_sources_config_is_an_error(tmp_path, monkeypatch):
    cli_store(tmp_path, monkeypatch)
    pol = write(tmp_path, HEADER + DEPARTMENT)
    missing = str(tmp_path / "missing.toml")
    result = CliRunner().invoke(
        app, ["report", "--policy", str(pol), "--config", missing]
    )
    assert result.exit_code == 1 and "not found" in result.output


def test_cli_report_shows_policy_line(tmp_path, monkeypatch):
    _, config = cli_store(tmp_path, monkeypatch)
    pol = write(tmp_path, HEADER + DEPARTMENT)
    run = CliRunner().invoke
    result = run(app, ["report", "--policy", str(pol), *config])
    assert result.exit_code == 0, result.output
    assert "E1 department: policy v1: recommend: hr is authoritative" in result.output
    assert "reviewer roles: hr-reviewer" in result.output
    result = run(app, ["report"])
    assert "E1 department: no authority policy: unresolved" in result.output
    out = tmp_path / "r.json"
    result = run(
        app, ["report-json", "--output", str(out), "--policy", str(pol), *config]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["policy"] == {"version": "v1", "in_force": True}
    assert data["discrepancies"][0]["policy"]["outcome"] == "recommend"


def test_cli_example_policy_and_sources(tmp_path, monkeypatch):
    """The example files, copied to the default paths, work together."""
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(tmp_path / "s.trig"))
    (tmp_path / "config").mkdir()
    for name in ("sources.toml", "policy.toml"):
        shutil.copy(EXAMPLES / name, tmp_path / "config" / name)
    run = CliRunner().invoke
    for workbook, source in (
        ("employees.xlsx", "hr-export"),
        ("employees-directory.xlsx", "people-directory"),
    ):
        ok = run(app, ["ingest-excel", str(EXAMPLES / workbook), "--source-id", source])
        assert ok.exit_code == 0, ok.output
    result = run(app, ["report"])
    assert result.exit_code == 0, result.output
    assert "E-1002 department: policy example-1: recommend: hr-export" in result.output


# -- review findings F1-F4 (regression) ----------------------------------------------


def test_bracketed_policy_text_is_printed_literally(tmp_path, monkeypatch):
    """F1: policy strings are not Rich markup. A review must not record its event
    and then fail on the confirmation line."""
    path, config = cli_store(tmp_path, monkeypatch)
    pol = write(
        tmp_path,
        'version = "v2 [/draft]"\neffective_from = 2026-01-01\n'
        + row(reviewer_roles='["[/x]", "[bold]lead"]'),
    )
    run = CliRunner().invoke
    result = run(app, ["report", "--policy", str(pol), *config])
    assert result.exit_code == 0, result.output
    assert "policy v2 [/draft]: recommend" in result.output
    assert "reviewer roles: [/x], [bold]lead" in result.output
    ok = run(
        app,
        [
            "review",
            "accept",
            str(dept("hr", "Eng")),
            *WHO,
            "--policy",
            str(pol),
            *config,
        ],
    )
    assert ok.exit_code == 0, ok.output
    assert "(policy v2 [/draft])" in ok.output
    assert audit_versions(path) == ["v2 [/draft]"]


def test_bracketed_text_in_policy_error_is_printed_literally(tmp_path, monkeypatch):
    _, config = cli_store(tmp_path, monkeypatch)
    pol = write(tmp_path, HEADER + row(property='"[/red]"'))
    result = CliRunner().invoke(app, ["report", "--policy", str(pol), *config])
    assert result.exit_code == 1
    assert "unknown property '[/red]'" in " ".join(result.output.split())
    assert "Traceback" not in result.output


@pytest.mark.parametrize("value", ['["department"]', '{ name = "department" }'])
def test_non_string_property_is_a_policy_error(tmp_path, value):
    """F2: an unhashable value must not escape as a TypeError."""
    with pytest.raises(PolicyError, match="unknown property"):
        policy(tmp_path, row(property=value))


def test_non_utf8_policy_is_a_policy_error(tmp_path):
    """F3."""
    path = tmp_path / "binary.toml"
    path.write_bytes(HEADER.encode() + b"\xff\xfe\n")
    with pytest.raises(PolicyError, match="cannot be read"):
        load_policy(path, SOURCES)


@pytest.mark.parametrize("command", ["review", "report", "report-json"])
def test_explicit_missing_policy_exits_and_writes_nothing(
    tmp_path, monkeypatch, command
):
    """F4: a mistyped --policy path is an error, never "no policy"."""
    path, config = cli_store(tmp_path, monkeypatch)
    before = path.read_bytes()
    args = {
        "review": ["review", "accept", str(dept("hr", "Eng")), *WHO],
        "report": ["report"],
        "report-json": ["report-json", "--output", str(tmp_path / "r.json")],
    }[command]
    missing = str(tmp_path / "polcy.toml")
    result = CliRunner().invoke(app, [*args, "--policy", missing, *config])
    assert result.exit_code == 1 and "policy file not found" in result.output
    assert path.read_bytes() == before
    assert not (tmp_path / "r.json").exists()
