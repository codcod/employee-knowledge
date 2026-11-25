"""Trust-scoped fact lookup (architecture §4.8), on synthetic records."""

import json
from datetime import UTC, datetime

import pytest
from rdflib.namespace import XSD
from typer.testing import CliRunner

from ek.adapters.base import EmployeeRecord, ReadResult
from ek.cli import app
from ek.config import SourceConfig
from ek.constants import EK, TRUSTED_GRAPH
from ek.graph.store import KnowledgeStore
from ek.ingest import assertion_uri, ingest
from ek.query import QueryError, Scope, query_facts
from ek.review import review


def load(store, source="hr", issuer="example-hr", **records):
    """records: employee_id -> department raw value."""
    cfg = SourceConfig(
        source,
        "excel",
        issuer=issuer,
        mapping_version="1",
        mapping={"employee_id": "id"},
    )
    rows = [
        EmployeeRecord(emp, {"department": dept}, f"{source}.xlsx#People!{n}")
        for n, (emp, dept) in enumerate(records.items(), start=2)
    ]
    ingest(
        store, cfg, ReadResult(f"{source}.xlsx", "a" * 64, rows, []), datetime.now(UTC)
    )


def dept(source, value, emp="E1"):
    return assertion_uri(source, emp, EK.department, XSD.string, value)


def act(store, a, action, **kw):
    review(store, a, action, reviewer="r", reason="Checked", **kw)


@pytest.fixture
def store(tmp_path):
    s = KnowledgeStore(tmp_path / "s.trig")
    load(s, "hr", E1="Engineering")
    load(s, "directory", E1="Product")
    return s


def trusted(store, **kw):
    return query_facts(store, scope=Scope.TRUSTED, **kw)


def test_scope_is_mandatory(store, tmp_path, monkeypatch):
    with pytest.raises(TypeError):
        query_facts(store)
    with pytest.raises(QueryError, match="Unknown scope"):
        query_facts(store, scope="everything")
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(tmp_path / "s.trig"))
    assert CliRunner().invoke(app, ["query"]).exit_code == 2
    assert CliRunner().invoke(app, ["query", "--scope", "everything"]).exit_code == 2


@pytest.mark.parametrize(
    "how", ["candidate", "needs-evidence", "rejected", "superseded"]
)
def test_trusted_scope_never_shows_unaccepted_values(store, how):
    act(store, dept("hr", "Engineering"), "accept")
    other = dept("directory", "Product")
    if how == "needs-evidence":
        act(store, other, "request-evidence")
    elif how == "rejected":
        act(store, other, "reject")
    elif how == "superseded":
        act(store, other, "accept")
        act(store, other, "supersede")
    [group] = trusted(store)
    assert group["values"] == ["Engineering"] and not group["conflict"]
    assert group["untrusted_candidates"] == 1
    out = json.dumps(trusted(store))
    assert "Product" not in out and str(other) not in out


def test_unaccepted_copy_of_an_accepted_value_is_not_counted(tmp_path):
    s = KnowledgeStore(tmp_path / "s.trig")
    load(s, "hr", E1="Engineering")
    load(s, "directory", E1="Engineering")
    act(s, dept("hr", "Engineering"), "accept")
    [group] = trusted(s)
    assert group["values"] == ["Engineering"] and group["untrusted_candidates"] == 0


def test_broken_projection_refuses_trusted_answer(store):
    other = dept("directory", "Product")
    for triple in store.facts(other):
        store.dataset.graph(TRUSTED_GRAPH).add(triple)
    with pytest.raises(QueryError, match="rebuild-projection"):
        trusted(store)
    [group] = query_facts(store, scope=Scope.ALL)
    assert group["values"] == ["Engineering", "Product"]


def test_all_scope_shows_every_value_with_its_state(store):
    act(store, dept("hr", "Engineering"), "accept")
    [group] = query_facts(store, scope=Scope.ALL)
    assert group["conflict"] and "untrusted_candidates" not in group
    assert [(f["value"], f["status"]) for f in group["facts"]] == [
        ("Product", "Candidate"),
        ("Engineering", "Accepted"),
    ]


def test_accepted_conflict_is_flagged_and_both_shown(store):
    act(store, dept("hr", "Engineering"), "accept")
    act(store, dept("directory", "Product"), "accept")
    [group] = trusted(store)
    assert group["conflict"] and group["values"] == ["Engineering", "Product"]
    assert group["untrusted_candidates"] == 0


def test_missing_trusted_value_is_disclosed(tmp_path):
    s = KnowledgeStore(tmp_path / "s.trig")
    load(s, "hr", E1="Engineering")
    [group] = trusted(s)
    assert group["facts"] == [] and group["values"] == []
    assert group["untrusted_candidates"] == 1


def test_facts_carry_provenance_and_latest_review(store):
    a = dept("hr", "Engineering")
    review(store, a, "accept", reviewer="r", reason="HR record", policy_version="v1")
    [f] = trusted(store)[0]["facts"]
    assert f["source"].endswith(":hr") and f["status"] == "Accepted"
    [obs] = f["observations"]
    assert obs["source_reference"] == "hr.xlsx#People!2" and obs["run"]
    r = f["latest_review"]
    assert (r["reviewer"], r["reason"], r["policy_version"], r["action"]) == (
        "r",
        "HR record",
        "v1",
        "Accept",
    )
    [unreviewed, _] = query_facts(store, scope=Scope.ALL)[0]["facts"]  # by source
    assert unreviewed["latest_review"] is None


def test_filters_and_issuers_are_never_merged(tmp_path):
    s = KnowledgeStore(tmp_path / "s.trig")
    load(s, "hr", E1="Engineering", E2="Sales")
    load(s, "contractors", issuer="example-agency", E1="Design")
    everything = query_facts(s, scope=Scope.ALL)
    assert len(everything) == 3
    e1 = query_facts(s, scope=Scope.ALL, employee_id="E1")
    assert sorted(g["issuer"] for g in e1) == ["example-agency", "example-hr"]
    [only] = query_facts(s, scope=Scope.ALL, employee_id="E1", issuer="example-agency")
    assert only["values"] == ["Design"]
    assert len(query_facts(s, scope=Scope.ALL, property="department")) == 3
    assert query_facts(s, scope=Scope.ALL, property="job_title") == []
    with pytest.raises(QueryError, match="Unknown property"):
        query_facts(s, scope=Scope.ALL, property="dept")


def test_cli_is_read_only_and_escapes_source_text(tmp_path, monkeypatch):
    path = tmp_path / "s.trig"
    s = KnowledgeStore(path)
    load(s, "hr", E1="[/x] :smile:")
    load(s, "directory", E1="Product")
    act(s, dept("hr", "[/x] :smile:"), "accept")
    s.save()
    before, size = path.read_bytes(), len(KnowledgeStore(path).dataset)
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(path))
    runner = CliRunner()

    run = runner.invoke(app, ["query", "--scope", "trusted"])
    assert run.exit_code == 0, run.output
    assert "[/x] :smile:" in run.output and "Product" not in run.output
    assert "1 unaccepted value(s) not shown; use --scope all" in run.output
    run = runner.invoke(app, ["query", "--scope", "all", "--json"])
    assert run.exit_code == 0
    assert {f["value"] for f in json.loads(run.output)[0]["facts"]} == {
        "[/x] :smile:",
        "Product",
    }
    run = runner.invoke(app, ["query", "--scope", "all", "--property", "dept"])
    assert run.exit_code == 1 and "Unknown property" in run.output

    assert path.read_bytes() == before
    assert len(KnowledgeStore(path).dataset) == size
