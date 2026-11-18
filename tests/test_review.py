"""Review events, state machine and projection (ADR-0002), on synthetic records."""

from datetime import UTC, datetime

import pytest
from rdflib import URIRef
from rdflib.namespace import RDF, XSD
from typer.testing import CliRunner

from ek.adapters.base import EmployeeRecord, ReadResult
from ek.cli import app
from ek.config import SourceConfig
from ek.constants import AUDIT_GRAPH, EK, TRUSTED_GRAPH, UNTRUSTED_GRAPH
from ek.graph.store import KnowledgeStore
from ek.identity import employee_uri
from ek.ingest import assertion_uri, ingest
from ek.review import TRANSITIONS, ReviewError, review

T0 = datetime(2026, 1, 1, tzinfo=UTC)
EMP = employee_uri("example-hr", "E-1")


def src(source_id):
    return SourceConfig(
        source_id,
        "excel",
        issuer="example-hr",
        mapping_version="1",
        mapping={"employee_id": "id"},
    )


def load(store, source_id="hr", dept="Eng"):
    record = EmployeeRecord("E-1", {"department": dept}, "people.xlsx#People!2")
    ingest(store, src(source_id), ReadResult("p.xlsx", "a" * 64, [record]), T0)
    return assertion_uri(source_id, "E-1", EK.department, XSD.string, dept)


@pytest.fixture
def store(tmp_path):
    return KnowledgeStore(tmp_path / "s.trig")


def act(store, a, action, **kw):
    return review(store, a, action, reviewer="reviewer-1", reason="Checked", **kw)


def drive(store, a, state):
    """Reach ``state`` from candidate using allowed transitions."""
    paths = {
        EK.Candidate: [],
        EK.Accepted: ["accept"],
        EK.Rejected: ["reject"],
        EK.NeedsEvidence: ["request-evidence"],
        EK.Superseded: ["accept", "supersede"],
    }
    for action in paths[state]:
        act(store, a, action)
    assert store.state(a) == state


STATES = [EK.Candidate, EK.Accepted, EK.Rejected, EK.NeedsEvidence, EK.Superseded]


@pytest.mark.parametrize("action", sorted(TRANSITIONS))
@pytest.mark.parametrize("start", STATES, ids=lambda s: str(s).rsplit("#")[-1])
def test_state_machine(store, action, start):
    a = load(store)
    drive(store, a, start)
    _, allowed, to_state = TRANSITIONS[action]
    events_before = len(store.events(a))
    if start in allowed:
        outcome = act(store, a, action)
        assert (outcome.from_state, outcome.to_state) == (start, to_state)
        assert store.state(a) == to_state
        expected = TRUSTED_GRAPH if to_state == EK.Accepted else UNTRUSTED_GRAPH
        assert store.graph_of(a) == expected
        assert store.check_projection() == []
    else:
        with pytest.raises(ReviewError, match="Cannot"):
            act(store, a, action)
        assert len(store.events(a)) == events_before


def test_event_records_who_why_and_sequence(store):
    a = load(store)
    first = act(store, a, "accept").event
    second = act(store, a, "reject").event
    audit = store.dataset.graph(AUDIT_GRAPH)
    assert [audit.value(e, EK.sequence).toPython() for e in (first, second)] == [1, 2]
    assert str(audit.value(first, EK.reviewer)) == "reviewer-1"
    assert str(audit.value(first, EK.reviewReason)) == "Checked"
    assert str(audit.value(first, EK.policyVersion)) == "none"
    assert audit.value(first, EK.fromState) == EK.Candidate


@pytest.mark.parametrize(("reviewer", "reason"), [(" ", "ok"), ("r", ""), ("r", "  ")])
def test_blank_reviewer_or_reason_is_refused(store, reviewer, reason):
    a = load(store)
    with pytest.raises(ReviewError, match="non-blank"):
        review(store, a, "accept", reviewer=reviewer, reason=reason)
    assert store.events() == []


def test_unknown_assertion_is_refused(store):
    with pytest.raises(ReviewError, match="Unknown assertion"):
        act(store, URIRef("urn:employee-knowledge:assertion:nope"), "accept")


def test_accept_moves_identity_and_leaves_competitors(store):
    eng, product = load(store, "hr"), load(store, "jira", "Product")
    act(store, eng, "accept")
    trusted = store.dataset.graph(TRUSTED_GRAPH)
    untrusted = store.dataset.graph(UNTRUSTED_GRAPH)
    assert (EMP, RDF.type, EK.Employee) in trusted
    assert (EMP, RDF.type, EK.Employee) in untrusted  # still used by the competitor
    assert store.graph_of(product) == UNTRUSTED_GRAPH
    assert store.state(product) == EK.Candidate
    assert (eng, None, None) not in untrusted


def test_orphaned_identity_is_removed_from_old_graph(store):
    a = load(store)
    act(store, a, "accept")
    assert (EMP, None, None) not in store.dataset.graph(UNTRUSTED_GRAPH)
    act(store, a, "reject")
    assert (EMP, None, None) not in store.dataset.graph(TRUSTED_GRAPH)


def test_accepting_conflicting_assertions_is_allowed_but_flagged(store):
    eng, product = load(store, "hr"), load(store, "jira", "Product")
    assert act(store, eng, "accept").accepted_conflicts == []
    assert act(store, product, "accept").accepted_conflicts == [eng]
    assert store.graph_of(eng) == store.graph_of(product) == TRUSTED_GRAPH


def test_reingest_after_accept_keeps_it_accepted_and_out_of_untrusted(store):
    a = load(store)
    act(store, a, "accept")
    load(store)
    assert store.state(a) == EK.Accepted
    assert (a, None, None) not in store.dataset.graph(UNTRUSTED_GRAPH)
    assert store.check_projection() == []


def test_supersede_by_records_link_and_checks_target(store):
    old, new = load(store, "hr"), load(store, "hr", "Product")
    act(store, old, "accept")
    event = act(store, old, "supersede", superseded_by=new).event
    assert store.dataset.graph(AUDIT_GRAPH).value(event, EK.supersededBy) == new
    with pytest.raises(ReviewError, match="only valid with supersede"):
        act(store, new, "accept", superseded_by=old)
    other = load(store, "hr", "Ops")
    act(store, other, "accept")
    with pytest.raises(ReviewError, match="Unknown superseding"):
        act(store, other, "supersede", superseded_by=URIRef("urn:x"))


def test_audit_survives_reload(tmp_path):
    path = tmp_path / "s.trig"
    store = KnowledgeStore(path)
    a = load(store)
    act(store, a, "accept")
    act(store, a, "supersede")
    store.save()
    reopened = KnowledgeStore(path)
    assert reopened.state(a) == EK.Superseded
    assert len(reopened.events(a)) == 2
    assert reopened.next_sequence() == 3
    assert reopened.check_projection() == []


def test_check_and_rebuild_projection_repair_drift(store):
    a = load(store)
    act(store, a, "accept")
    # Simulate drift: copy the accepted assertion back into the untrusted graph.
    untrusted = store.dataset.graph(UNTRUSTED_GRAPH)
    for triple in store.facts(a):
        untrusted.add(triple)
    assert store.check_projection() == [(a, UNTRUSTED_GRAPH, EK.Accepted)]
    assert store.rebuild_projection() == 1
    assert store.check_projection() == []
    assert store.graph_of(a) == TRUSTED_GRAPH and (a, None, None) not in untrusted


def test_cli_review_and_rebuild(tmp_path, monkeypatch):
    path = tmp_path / "s.trig"
    monkeypatch.setenv("EMPLOYEE_KNOWLEDGE_STORE", str(path))
    store = KnowledgeStore(path)
    a = load(store)
    store.save()
    run = CliRunner().invoke
    who = ["--reviewer", "reviewer-1", "--reason", "Checked"]
    ok = run(app, ["review", "accept", str(a), *who])
    assert ok.exit_code == 0, ok.output
    assert KnowledgeStore(path).state(a) == EK.Accepted
    bad = run(app, ["review", "request-evidence", str(a), *who])
    assert bad.exit_code == 1 and "Cannot" in bad.output
    blank = run(app, ["review", "reject", str(a), "--reviewer", "r", "--reason", " "])
    assert blank.exit_code == 1
    assert KnowledgeStore(path).state(a) == EK.Accepted
    assert run(app, ["rebuild-projection", "--check"]).exit_code == 0
    assert run(app, ["rebuild-projection"]).exit_code == 0
