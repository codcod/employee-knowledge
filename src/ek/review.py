"""Review actions (ADR-0002). The only way trust state changes."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, XSD

from .constants import EK
from .graph.store import KnowledgeStore
from .validation import validate

# action -> (action IRI, allowed from-states, to-state)
TRANSITIONS = {
    "accept": (EK.Accept, {EK.Candidate, EK.NeedsEvidence, EK.Superseded}, EK.Accepted),
    "reject": (EK.Reject, {EK.Candidate, EK.NeedsEvidence, EK.Accepted}, EK.Rejected),
    "request-evidence": (EK.RequestEvidence, {EK.Candidate}, EK.NeedsEvidence),
    "supersede": (EK.Supersede, {EK.Accepted}, EK.Superseded),
    "reopen": (EK.Reopen, {EK.Rejected}, EK.Candidate),
}


class ReviewError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewOutcome:
    event: URIRef
    from_state: URIRef
    to_state: URIRef
    graph: URIRef
    accepted_conflicts: list[URIRef]


def label(state: URIRef) -> str:
    return str(state).rsplit("#", 1)[-1]


def review(
    store: KnowledgeStore,
    assertion: URIRef,
    action: str,
    *,
    reviewer: str,
    reason: str,
    superseded_by: URIRef | None = None,
    policy_version: str = "none",
) -> ReviewOutcome:
    """Record one review event and update the projection, in memory. Caller saves.
    ``reviewer`` is a local label, not authentication. ``policy_version`` is the
    authority policy in force (ADR-0010), or "none"."""
    if action not in TRANSITIONS:
        raise ReviewError(f"Unknown review action '{action}'")
    if not reviewer.strip():
        raise ReviewError("A non-blank reviewer label is required")
    if not reason.strip():
        raise ReviewError("A non-blank review reason is required")
    if store.graph_of(assertion) is None:
        raise ReviewError(f"Unknown assertion {assertion}")
    action_iri, allowed, to_state = TRANSITIONS[action]
    from_state = store.state(assertion)
    if from_state not in allowed:
        raise ReviewError(
            f"Cannot {action} an assertion in state {label(from_state)}; "
            f"allowed from: {sorted(label(s) for s in allowed)}"
        )
    facts = store.facts(assertion)
    if superseded_by is not None:
        if action != "supersede":
            raise ReviewError("--by is only valid with supersede")
        if superseded_by == assertion or store.graph_of(superseded_by) is None:
            raise ReviewError(f"Unknown superseding assertion {superseded_by}")
        other = store.facts(superseded_by)
        for p in (EK.aboutEmployee, EK.predicate):
            if other.value(superseded_by, p) != facts.value(assertion, p):
                raise ReviewError(
                    "A superseding assertion must be about the same employee and "
                    "property"
                )
        facts += other

    event = URIRef(f"urn:employee-knowledge:review:{uuid.uuid4()}")
    g = Graph()
    for t in (EK.ReviewEvent, PROV.Activity):
        g.add((event, RDF.type, t))
    g.add((event, PROV.used, assertion))
    g.add((event, EK.reviewAction, action_iri))
    g.add((event, EK.fromState, from_state))
    g.add((event, EK.toState, to_state))
    g.add((event, EK.reviewer, Literal(reviewer.strip())))
    g.add((event, EK.reviewReason, Literal(reason.strip())))
    g.add((event, EK.policyVersion, Literal(policy_version)))
    g.add((event, EK.sequence, Literal(store.next_sequence())))
    g.add((event, PROV.endedAtTime, Literal(datetime.now(UTC), datatype=XSD.dateTime)))
    if superseded_by is not None:
        g.add((event, EK.supersededBy, superseded_by))
    if model := [f for f in validate(g + facts) if f.kind == "model"]:
        raise ReviewError(
            "Review event failed validation: "
            + "; ".join(f"{f.shape} {f.path}" for f in model)
        )

    store.add_event(g)
    graph = store.project(assertion)
    conflicts = store.accepted_conflicts(assertion) if to_state == EK.Accepted else []
    return ReviewOutcome(event, from_state, to_state, graph, conflicts)
