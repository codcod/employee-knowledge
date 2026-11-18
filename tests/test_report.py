"""Discrepancy report (architecture §4.6), on synthetic records."""

import json
from datetime import UTC, datetime

from rdflib.namespace import XSD
from typer.testing import CliRunner

import ek.ingest
from ek.adapters.base import EmployeeRecord, QuarantinedRecord, ReadResult
from ek.cli import app
from ek.config import SourceConfig
from ek.constants import EK
from ek.graph.store import KnowledgeStore
from ek.ingest import assertion_uri, ingest
from ek.reconcile import build_report
from ek.review import review
from ek.validation import Finding


def load(store, source="hr", day=1, quarantined=(), **records):
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
    result = ReadResult(f"{source}.xlsx", "a" * 64, rows, list(quarantined))
    ingest(store, cfg, result, datetime(2026, 1, day, tzinfo=UTC))


def dept(source, value, emp="E1"):
    return assertion_uri(source, emp, EK.department, XSD.string, value)


def accept(store, a):
    review(store, a, "accept", reviewer="r", reason="Checked")


def test_cross_source_conflict_shows_evidence_and_states(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", E1=" Engineering ")
    load(store, "directory", E1="Product")
    [item] = build_report(store)["discrepancies"]
    assert item["employee_id"] == "E1" and item["values"] == ["Engineering", "Product"]
    assert not item["accepted_conflict"]
    by_source = {f["source"].rsplit(":")[-1]: f for f in item["facts"]}
    hr = by_source["hr"]
    assert (hr["status"], hr["observed_in_latest_run"]) == ("Candidate", True)
    [obs] = hr["observations"]
    assert obs["raw_value"] == " Engineering "
    assert obs["source_reference"] == "hr.xlsx#People!2"
    assert obs["validation"] == "Conforms" and obs["observed_at"] is None


def test_values_equal_after_trimming_are_not_a_discrepancy(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", E1=" Engineering")
    load(store, "directory", E1="Engineering  ")
    assert build_report(store)["discrepancies"] == []


def test_case_differences_are_still_reported(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", E1="Engineering")
    load(store, "directory", E1="engineering")
    assert len(build_report(store)["discrepancies"]) == 1


def test_accepted_conflict_is_flagged_but_same_value_is_not(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", E1="Eng", E2="Ops")
    load(store, "directory", E1="Product", E2="Ops")
    load(store, "third", E2="Ops")
    accept(store, dept("hr", "Eng"))
    assert not build_report(store)["discrepancies"][0]["accepted_conflict"]
    accept(store, dept("directory", "Product"))
    accept(store, dept("hr", "Ops", "E2"))
    accept(store, dept("third", "Ops", "E2"))
    [item] = build_report(store)["discrepancies"]
    assert item["employee_id"] == "E1" and item["accepted_conflict"]


def test_value_gone_from_latest_run_is_flagged_and_keeps_state(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", day=1, E1="Eng", E2="Ops")
    accept(store, dept("hr", "Ops", "E2"))
    load(store, "hr", day=2, E1="Product")  # E1 changed, E2 gone
    report = build_report(store)
    gone = {(f["employee_id"], f["value"], f["status"]) for f in report["not_observed"]}
    assert gone == {("E1", "Eng", "Candidate"), ("E2", "Ops", "Accepted")}
    [item] = report["discrepancies"]  # old and new E1 value from the same source
    assert item["values"] == ["Eng", "Product"]
    old = next(f for f in item["facts"] if f["value"] == "Eng")
    assert len(old["observations"]) == 1  # history kept from run 1


def test_other_sources_runs_do_not_count_as_absence(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", day=1, E1="Eng")
    load(store, "directory", day=2, E2="Ops")
    assert build_report(store)["not_observed"] == []


def test_validation_violations_are_listed(tmp_path, monkeypatch):
    bad = dept("hr", "Eng")
    finding = Finding("value", str(bad), None, "bad value", "shape")
    monkeypatch.setattr(ek.ingest, "validate", lambda g: [finding])
    store = KnowledgeStore(tmp_path / "s.trig")
    load(store, "hr", E1="Eng", E2="Ops")
    [f] = build_report(store)["validation_violations"]
    assert f["assertion"] == str(bad)
    assert f["observations"][0]["validation_messages"] == ["bad value"]


def test_quarantined_rows_come_from_latest_run_only(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    old = QuarantinedRecord("hr.xlsx#People!9", "missing employee ID")
    new = QuarantinedRecord("hr.xlsx#People!4", "missing employee ID")
    load(store, "hr", day=1, quarantined=[old], E1="Eng")
    load(store, "hr", day=2, quarantined=[new], E1="Eng")
    [q] = build_report(store)["quarantined"]
    assert (q["source_reference"], q["reason"]) == (
        "hr.xlsx#People!4",
        "missing employee ID",
    )


def test_cli_report_and_json(tmp_path, monkeypatch):
    path = tmp_path / "s.trig"
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(path))
    store = KnowledgeStore(path)
    q = QuarantinedRecord("hr.xlsx#People!7", "missing employee ID")
    load(store, "hr", day=1, E1="Eng", E2="Ops")
    load(store, "hr", day=2, quarantined=[q], E1="Eng")
    load(store, "directory", day=2, E1="Product")
    store.save()
    table = CliRunner().invoke(app, ["report"])
    assert table.exit_code == 0, table.output
    for text in ("Discrepancies", "Not observed", "Quarantined", "People!7"):
        assert text in table.output
    out = tmp_path / "r.json"
    assert CliRunner().invoke(app, ["report-json", "--output", str(out)]).exit_code == 0
    data = json.loads(out.read_text())
    assert set(data) == {
        "discrepancies",
        "not_observed",
        "validation_violations",
        "quarantined",
    }
    assert data == build_report(KnowledgeStore(path))
