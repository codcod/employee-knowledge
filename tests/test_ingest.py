"""Store and ingestion runs (ADR-0001/3/4/5/6), on synthetic records."""

import hashlib
from datetime import UTC, datetime

import pytest
from rdflib import Literal
from rdflib.compare import isomorphic
from rdflib.namespace import PROV, RDF, XSD

import ek.ingest
from ek.adapters.base import EmployeeRecord, QuarantinedRecord, ReadResult
from ek.config import SourceConfig
from ek.constants import EK, FIELD_PREDICATES, UNTRUSTED_GRAPH
from ek.graph.store import KnowledgeStore
from ek.identity import employee_uri, source_uri
from ek.ingest import IngestError, assertion_uri, ingest
from ek.reconcile import build_report
from ek.validation import Finding

T0 = datetime(2026, 1, 1, tzinfo=UTC)
SHA = "a" * 64


def hr(**kw):
    return SourceConfig(
        "hr",
        "excel",
        issuer="example-hr",
        mapping_version="1",
        mapping={"employee_id": "id", **{f: f for f in FIELD_PREDICATES}},
        **kw,
    )


def read(*records, quarantined=()):
    return ReadResult("people.xlsx", SHA, list(records), list(quarantined))


def rec(emp="E-1", row=2, **values):
    return EmployeeRecord(emp, values, f"people.xlsx#People!{row}")


def untrusted(store):
    return store.dataset.graph(UNTRUSTED_GRAPH)


def assertions(store):
    return {a for _, a, _ in store.assertions()}


def only_run(store):
    [(run, graph)] = store.completed_runs(source_uri("hr"))
    return run, graph


def test_run_assertions_and_observations_follow_the_model(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    summary = ingest(
        store,
        hr(),
        read(
            rec(department=" Eng "),
            quarantined=[
                QuarantinedRecord("people.xlsx#People!3", "missing employee ID")
            ],
        ),
        T0,
    )
    assert (summary.observations, summary.new_assertions, summary.quarantined) == (
        1,
        1,
        1,
    )
    a = assertion_uri("hr", "E-1", EK.department, XSD.string, "Eng")
    g = untrusted(store)
    emp = employee_uri("example-hr", "E-1")
    assert g.value(a, EK.aboutEmployee) == emp
    assert g.value(a, EK.value) == Literal("Eng", datatype=XSD.string)
    assert g.value(emp, EK.issuer) == Literal("example-hr")
    run, rg = only_run(store)
    assert rg.value(rg.value(run, PROV.used), EK.sha256) == Literal(SHA)
    assert rg.value(run, PROV.startedAtTime).toPython() == T0
    [obs] = rg.subjects(EK.ofAssertion, a)
    assert rg.value(obs, EK.rawValue) == Literal(" Eng ")
    assert rg.value(obs, EK.sourceReference) == Literal("people.xlsx#People!2")
    assert rg.value(obs, EK.validationResult) == EK.Conforms
    assert rg.value(obs, EK.observedAt) is None  # never defaulted
    [q] = rg.subjects(RDF.type, EK.QuarantinedRecord)
    assert rg.value(q, EK.quarantineReason) == Literal("missing employee ID")
    # Nothing on the assertion itself is mutable provenance.
    assert not {EK.observedAt, EK.sourceReference} & set(g.predicates(a))


def test_assertion_id_uses_the_unit_separator():
    raw = "\x1f".join(["hr", "E-1", str(EK.department), str(XSD.string), "Eng"])
    expected = (
        "urn:employee-knowledge:assertion:" + hashlib.sha256(raw.encode()).hexdigest()
    )
    assert str(assertion_uri("hr", "E-1", EK.department, XSD.string, "Eng")) == expected


def test_source_observation_time_is_kept(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    r = EmployeeRecord("E-1", {"department": "Eng"}, "ref", "2025-12-31T09:00:00Z")
    ingest(store, hr(), read(r), T0)
    _, rg = only_run(store)
    [obs] = rg.subjects(RDF.type, EK.Observation)
    assert rg.value(obs, EK.observedAt).toPython() == datetime(
        2025, 12, 31, 9, tzinfo=UTC
    )


def test_reingestion_is_idempotent_and_reorder_stable(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    first = read(rec("E-1", 2, department="Eng"), rec("E-2", 3, department="Ops"))
    ingest(store, hr(), first, T0)
    before = set(untrusted(store))
    reordered = read(rec("E-2", 2, department="Ops "), rec("E-1", 3, department="Eng"))
    summary = ingest(store, hr(), reordered, T0.replace(day=2))
    assert summary.new_assertions == 0
    assert set(untrusted(store)) == before
    assert len(store.completed_runs(source_uri("hr"))) == 2


def test_changed_value_adds_assertion_and_old_is_not_observed(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    ingest(store, hr(), read(rec(department="Eng")), T0)
    ingest(store, hr(), read(rec(department="Product")), T0.replace(day=2))
    old = assertion_uri("hr", "E-1", EK.department, XSD.string, "Eng")
    new = assertion_uri("hr", "E-1", EK.department, XSD.string, "Product")
    assert {old, new} <= assertions(store)  # evidence is never erased
    (_, first), (_, latest) = store.completed_runs(source_uri("hr"))
    assert old in store.observed(first)
    assert old not in store.observed(latest) and new in store.observed(latest)


def test_issuers_never_merge(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    ingest(store, hr(), read(rec(department="Eng")), T0)
    other = SourceConfig(
        "jira",
        "excel",
        issuer="jira",
        mapping_version="1",
        mapping={"employee_id": "id", **{f: f for f in FIELD_PREDICATES}},
    )
    ingest(store, other, read(rec(department="Eng")), T0)
    employees = set(untrusted(store).subjects(RDF.type, EK.Employee))
    assert employees == {employee_uri("example-hr", "E-1"), employee_uri("jira", "E-1")}


def test_conflict_between_sources_stays_visible(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    ingest(store, hr(), read(rec(department="Eng")), T0)
    other = SourceConfig(
        "hr2",
        "excel",
        issuer="example-hr",
        mapping_version="1",
        mapping={"employee_id": "id", **{f: f for f in FIELD_PREDICATES}},
    )
    ingest(store, other, read(rec(department="Product")), T0)
    [item] = build_report(store)["discrepancies"]
    assert item["values"] == ["Eng", "Product"]
    assert all(f["status"] == "Candidate" for f in item["facts"])


def test_reload_round_trip(tmp_path):
    path = tmp_path / "s.trig"
    store = KnowledgeStore(path)
    ingest(store, hr(), read(rec(department="Eng", full_name="Alex Example")), T0)
    store.save()
    reopened = KnowledgeStore(path)
    for graph in store.dataset.graphs():
        assert isomorphic(graph, reopened.dataset.graph(graph.identifier))
    assert len(reopened.completed_runs(source_uri("hr"))) == 1


def test_model_finding_aborts_and_stores_nothing(tmp_path):
    path = tmp_path / "s.trig"
    store = KnowledgeStore(path)
    ingest(store, hr(), read(rec(department="Eng")), T0)
    store.save()
    saved = path.read_bytes()
    broken = SourceConfig(
        "hr",
        "excel",
        issuer="example-hr",
        mapping_version=" ",
        mapping={"employee_id": "id", **{f: f for f in FIELD_PREDICATES}},
    )
    with pytest.raises(IngestError) as exc:
        ingest(store, broken, read(rec(department="Ops")), T0)
    assert {f.path for f in exc.value.findings} == {str(EK.mappingVersion)}
    assert len(store.completed_runs(source_uri("hr"))) == 1
    assert path.read_bytes() == saved


def test_value_finding_is_recorded_and_assertion_kept(tmp_path, monkeypatch):
    a = assertion_uri("hr", "E-1", EK.department, XSD.string, "Eng")
    finding = Finding("value", str(a), None, "bad value", str(EK.AssertionValueShape))
    monkeypatch.setattr(ek.ingest, "validate", lambda g: [finding])
    store = KnowledgeStore(tmp_path / "s.trig")
    summary = ingest(store, hr(), read(rec(department="Eng", full_name="Alex")), T0)
    assert summary.value_violations == 1
    assert store.graph_of(a) == UNTRUSTED_GRAPH
    _, rg = only_run(store)
    results = {
        rg.value(o, EK.ofAssertion): rg.value(o, EK.validationResult)
        for o in rg.subjects(RDF.type, EK.Observation)
    }
    assert results[a] == EK.Violation
    assert set(results.values()) == {EK.Violation, EK.Conforms}
    [obs] = rg.subjects(EK.ofAssertion, a)
    assert rg.value(obs, EK.validationMessage) == Literal("bad value")


def test_failed_save_keeps_previous_store(tmp_path, monkeypatch):
    path = tmp_path / "s.trig"
    store = KnowledgeStore(path)
    ingest(store, hr(), read(rec(department="Eng")), T0)
    store.save()
    saved = path.read_bytes()
    ingest(store, hr(), read(rec(department="Ops")), T0)

    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(store.dataset, "serialize", boom)
    with pytest.raises(OSError):
        store.save()
    assert path.read_bytes() == saved
    assert [p.name for p in tmp_path.iterdir()] == ["s.trig"]


def test_email_is_lowercased_and_other_fields_keep_case(tmp_path):
    store = KnowledgeStore(tmp_path / "s.trig")
    ingest(
        store, hr(), read(rec(work_email=" Taylor@Example.COM ", department="Eng")), T0
    )
    values = {str(o) for _, _, o in untrusted(store).triples((None, EK.value, None))}
    assert values == {"taylor@example.com", "Eng"}
    raw = {str(o) for _, _, o, _ in store.dataset.quads((None, EK.rawValue, None))}
    assert " Taylor@Example.COM " in raw
