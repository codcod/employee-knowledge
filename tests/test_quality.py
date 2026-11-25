"""Data-quality and freshness findings (EK-003), on synthetic records."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from rdflib.namespace import XSD
from typer.testing import CliRunner

import ek.ingest
from ek.adapters.base import EmployeeRecord, QuarantinedRecord, ReadResult
from ek.cli import app
from ek.config import SourceConfig
from ek.constants import EK, FIELD_PREDICATES
from ek.graph.store import KnowledgeStore
from ek.ingest import assertion_uri, ingest
from ek.policy import Policy, PropertyPolicy
from ek.quality import UNKNOWN, UNKNOWN_TZ, findings
from ek.reconcile import build_report
from ek.review import review
from ek.validation import Finding

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def load(store, source="hr", issuer="example-hr", day=1, quarantined=(), **records):
    """records: employee_id -> {field: raw} or (values, observed_at)."""
    cfg = SourceConfig(
        source,
        "excel",
        issuer=issuer,
        mapping_version="1",
        mapping={"employee_id": "id", **{f: f for f in FIELD_PREDICATES}},
    )
    rows = []
    for n, (emp, spec) in enumerate(records.items(), start=2):
        values, observed_at = spec if isinstance(spec, tuple) else (spec, None)
        rows.append(EmployeeRecord(emp, values, f"{source}.xlsx#S!{n}", observed_at))
    result = ReadResult(f"{source}.xlsx", "a" * 64, rows, list(quarantined))
    ingest(store, cfg, result, datetime(2026, 1, day, tzinfo=UTC))


def policy(effective=date(2026, 1, 1), freshness=None, required=False):
    row = PropertyPolicy(
        "department",
        EK.department,
        (),
        (),
        "manual",
        freshness_days=freshness,
        required=required,
    )
    return Policy("v1", effective, {EK.department: row})


def of(category, store, pol=None, now=NOW):
    return [f for f in findings(store, pol, now) if f["category"] == category]


def store_(tmp_path):
    return KnowledgeStore(tmp_path / "s.trig")


# -- invalid-value ---------------------------------------------------------


def test_invalid_value_has_its_source_reference(tmp_path, monkeypatch):
    bad = assertion_uri("hr", "E1", EK.department, XSD.string, "Eng")
    finding = Finding("value", str(bad), None, "bad value", "shape")
    monkeypatch.setattr(ek.ingest, "validate", lambda g: [finding])
    store = store_(tmp_path)
    load(store, E1={"department": "Eng"}, E2={"department": "Ops"})
    [f] = of("invalid-value", store)
    assert (f["employee_id"], f["property"]) == ("E1", str(EK.department))
    assert f["evidence"] == [
        {
            "assertion": str(bad),
            "source": f["evidence"][0]["source"],
            "source_reference": "hr.xlsx#S!2",
        }
    ]


def test_conforming_values_give_no_invalid_finding(tmp_path):
    store = store_(tmp_path)
    load(store, E1={"department": "Eng"})
    assert of("invalid-value", store) == []


# -- unresolved-identity ---------------------------------------------------


def test_unresolved_identity_from_latest_run_only(tmp_path):
    store = store_(tmp_path)
    old = QuarantinedRecord("hr.xlsx#S!9", "missing employee ID")
    dup = QuarantinedRecord("hr.xlsx#S!4", "duplicate employee ID")
    load(store, day=1, quarantined=[old], E1={"department": "Eng"})
    load(store, day=2, quarantined=[dup], E1={"department": "Eng"})
    [f] = of("unresolved-identity", store)
    assert f["evidence"] == [
        {
            "source": "urn:employee-knowledge:source:hr",
            "source_reference": "hr.xlsx#S!4",
        }
    ]
    assert "duplicate employee ID" in f["rationale"]
    assert "employee_id" not in f


# -- broken-manager-reference ----------------------------------------------


def test_manager_known_from_another_source_of_same_issuer_resolves(tmp_path):
    store = store_(tmp_path)
    load(store, "hr", E1={"manager_employee_id": "E9"})
    load(store, "directory", E9={"department": "Ops"})
    assert of("broken-manager-reference", store) == []


def test_manager_under_another_issuer_or_missing_is_broken(tmp_path):
    store = store_(tmp_path)
    load(store, "hr", E1={"manager_employee_id": "E9"}, E2={"manager_employee_id": "X"})
    load(store, "other", issuer="other-hr", E9={"department": "Ops"})
    broken = of("broken-manager-reference", store)
    assert [f["employee_id"] for f in broken] == ["E1", "E2"]
    assert broken[0]["evidence"][0]["source_reference"] == "hr.xlsx#S!2"


def test_accepted_manager_assertion_still_gets_its_finding(tmp_path):
    store = store_(tmp_path)
    load(store, E1={"manager_employee_id": "E9"})
    manager = assertion_uri("hr", "E1", EK.managerEmployeeId, XSD.string, "E9")
    review(store, manager, "accept", reviewer="r", reason="Checked")
    [f] = of("broken-manager-reference", store)
    assert f["evidence"][0]["assertion"] == str(manager)
    assert "status" not in f and "graph" not in f  # quality is not trust


# -- missing-required ------------------------------------------------------


def test_required_property_from_one_source_is_enough(tmp_path):
    store = store_(tmp_path)
    load(store, "hr", E1={"department": "Eng"})
    load(store, "directory", E1={"job_title": "Dev"})
    assert of("missing-required", store, policy(required=True)) == []


def test_required_property_seen_only_in_an_older_run_is_missing(tmp_path):
    store = store_(tmp_path)
    load(store, day=1, E1={"department": "Eng", "job_title": "Dev"})
    load(store, day=2, E1={"job_title": "Dev"})
    [f] = of("missing-required", store, policy(required=True))
    assert (f["employee_id"], f["property"]) == ("E1", str(EK.department))
    assert [e["source_reference"] for e in f["evidence"]] == ["hr.xlsx#S!2"]


def test_required_checks_need_a_policy_in_force(tmp_path):
    store = store_(tmp_path)
    load(store, E1={"job_title": "Dev"})
    assert len(of("missing-required", store, policy(required=True))) == 1
    assert of("missing-required", store, None) == []
    future = policy(effective=date(2026, 7, 1), required=True)
    assert of("missing-required", store, future) == []


# -- stale and freshness-unknown -------------------------------------------


def test_freshness_window_boundary(tmp_path):
    store = store_(tmp_path)
    edge = NOW - timedelta(days=30)
    load(
        store,
        E1=({"department": "Eng"}, edge.isoformat()),
        E2=({"department": "Ops"}, (edge - timedelta(seconds=1)).isoformat()),
    )
    [f] = of("stale", store, policy(freshness=30))
    assert f["employee_id"] == "E2"
    assert f["evidence"][0]["observed_at"] == (edge - timedelta(seconds=1)).isoformat()
    assert of("freshness-unknown", store, policy(freshness=30)) == []


def test_newest_observation_time_counts(tmp_path):
    store = store_(tmp_path)
    load(store, day=1, E1=({"department": "Eng"}, "2025-01-01T00:00:00+00:00"))
    load(store, day=2, E1=({"department": "Eng"}, "2026-05-30T00:00:00+00:00"))
    assert of("stale", store, policy(freshness=30)) == []


def test_no_observation_time_is_freshness_unknown(tmp_path):
    store = store_(tmp_path)
    load(store, E1={"department": "Eng"})
    [f] = of("freshness-unknown", store, policy(freshness=30))
    assert f["rationale"] == UNKNOWN and "ingestion time is not used" in UNKNOWN


def test_time_without_timezone_is_freshness_unknown_not_stale(tmp_path):
    store = store_(tmp_path)
    load(store, E1=({"department": "Eng"}, "2020-01-01T00:00:00"))
    pol = policy(freshness=30)
    assert of("stale", store, pol) == []
    [f] = of("freshness-unknown", store, pol)
    assert f["rationale"] == UNKNOWN_TZ
    assert f["evidence"][0]["observed_at"] == "2020-01-01T00:00:00"


def test_newer_time_without_timezone_is_never_stale_on_an_older_one(tmp_path):
    store = store_(tmp_path)
    load(store, day=1, E1=({"department": "Eng"}, "2020-01-01T00:00:00+00:00"))
    load(store, day=2, E1=({"department": "Eng"}, "2026-05-31T00:00:00"))
    pol = policy(freshness=30)
    assert of("stale", store, pol) == []
    [f] = of("freshness-unknown", store, pol)
    assert f["rationale"] == UNKNOWN_TZ
    assert [e["observed_at"] for e in f["evidence"]] == ["2026-05-31T00:00:00"]


def test_naive_now_is_refused(tmp_path):
    store = store_(tmp_path)
    load(store, E1={"department": "Eng"})
    with pytest.raises(ValueError, match="timezone"):
        findings(store, policy(freshness=30), datetime(2026, 6, 1))


def test_report_uses_one_date_for_policy_and_findings(tmp_path):
    store = store_(tmp_path)
    load(store, E1={"job_title": "Dev"})
    pol = policy(required=True)
    before = build_report(store, pol, today=date(2025, 12, 31))
    assert before["policy"]["in_force"] is False
    assert [f for f in before["findings"] if f["category"] == "missing-required"] == []
    after = build_report(store, pol, now=NOW)
    assert after["policy"]["in_force"] is True
    assert [f["category"] for f in after["findings"]] == ["missing-required"]


def test_property_without_window_gets_no_freshness_finding(tmp_path):
    store = store_(tmp_path)
    load(store, E1=({"department": "Eng"}, "2020-01-01T00:00:00+00:00"))
    load(store, "directory", E1={"department": "Ops"})
    pol = policy(required=True)
    assert of("stale", store, pol) == of("freshness-unknown", store, pol) == []


# -- invariants ------------------------------------------------------------


def test_findings_change_nothing_and_are_complete(tmp_path):
    store = store_(tmp_path)
    q = QuarantinedRecord("hr.xlsx#S!9", "missing employee ID")
    load(store, quarantined=[q], E1={"manager_employee_id": "E9", "job_title": "Dev"})
    load(store, "directory", E1=({"department": "Ops"}, "2020-01-01T00:00:00+00:00"))
    load(store, "third", E2={"department": "Eng"})
    title = assertion_uri("hr", "E1", EK.jobTitle, XSD.string, "Dev")
    review(store, title, "accept", reviewer="r", reason="Checked")
    assertions = [a for _, a, _ in store.assertions()]
    states = {a: store.state(a) for a in assertions}
    size = len(store.dataset)
    found = findings(store, policy(freshness=30, required=True), NOW)
    assert {f["category"] for f in found} == {
        "unresolved-identity",
        "broken-manager-reference",
        "stale",
        "freshness-unknown",
    }
    assert len(store.dataset) == size
    assert {a: store.state(a) for a in assertions} == states
    assert store.check_projection() == []
    for f in found:
        assert f["category"] and f["rationale"] and f["evidence"]


# -- CLI -------------------------------------------------------------------


def test_cli_shows_findings_table_and_json_key(tmp_path, monkeypatch):
    path = tmp_path / "s.trig"
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(path))
    store = KnowledgeStore(path)
    q = QuarantinedRecord("hr.xlsx#S![bold]9", "missing employee ID")
    load(store, quarantined=[q], E1={"manager_employee_id": "E9"})
    load(store, "directory", quarantined=[q])  # same reference, other source
    store.save()
    out = CliRunner().invoke(app, ["report"])
    assert out.exit_code == 0, out.output
    for text in (
        "Data-quality findings",
        "broken-manager-reference",
        "hr: hr.xlsx#S![bold]9",  # escaped, printed as written, with its source
        "directory: hr.xlsx#S![bold]9",
        "Required and freshness checks are off",
    ):
        assert text in out.output
    assert "Invalid values" not in out.output
    (tmp_path / "sources.toml").write_text(
        '[[sources]]\nid = "hr"\nkind = "excel"\nissuer = "example-hr"\n'
        'sheet = "S"\nmapping_version = "1"\n'
        '[sources.mapping]\nemployee_id = "id"\n',
        encoding="utf-8",
    )
    (tmp_path / "policy.toml").write_text(
        'version = "v1"\neffective_from = 2026-01-01\n[[properties]]\n'
        'property = "department"\nauthoritative = []\nconflict_rule = "manual"\n'
        "required = true\n",
        encoding="utf-8",
    )
    args = ["report", "--policy", "policy.toml", "--config", "sources.toml"]
    on = CliRunner().invoke(app, args)
    assert on.exit_code == 0, on.output
    assert "missing-required" in on.output
    assert "checks are off" not in on.output
    report = tmp_path / "r.json"
    assert (
        CliRunner().invoke(app, ["report-json", "--output", str(report)]).exit_code == 0
    )
    data = json.loads(report.read_text())
    assert {f["category"] for f in data["findings"]} == {
        "broken-manager-reference",
        "unresolved-identity",
    }
