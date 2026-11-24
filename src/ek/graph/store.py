"""The only code that touches RDF storage (ADR-0005)."""

import os
import tempfile
from pathlib import Path

from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import PROV, RDF

from ..constants import (
    AUDIT_GRAPH,
    EK,
    RUN_GRAPH_PREFIX,
    TRUSTED_GRAPH,
    UNTRUSTED_GRAPH,
)


class KnowledgeStore:
    """One TriG file, loaded whole. ponytail: one writer at a time, no lock (ADR-0005)."""

    def __init__(self, path):
        self.path = Path(path)
        self.dataset = Dataset()
        if self.path.exists():
            self.dataset.parse(self.path, format="trig")
        self.dataset.bind("ek", EK)
        self.dataset.bind("prov", PROV)

    # -- writing -----------------------------------------------------------

    def add_run(self, run_graph: URIRef, run: Graph, facts: Graph) -> int:
        """Store a completed run graph, and add its assertions to the untrusted graph
        unless they are already in a trust graph (ADR-0002). Returns how many are new."""
        target = self.dataset.graph(run_graph)
        for triple in run:
            target.add(triple)
        untrusted = self.dataset.graph(UNTRUSTED_GRAPH)
        new = 0
        for assertion in set(facts.subjects(RDF.type, EK.FactAssertion)):
            if self.graph_of(assertion) is not None:
                continue
            new += 1
            for subject in (
                assertion,
                facts.value(assertion, EK.aboutEmployee),
                facts.value(assertion, EK.fromSource),
            ):
                for p, o in facts.predicate_objects(subject):
                    untrusted.add((subject, p, o))
        return new

    def add_event(self, event: Graph) -> None:
        """Append a review event to the audit graph. Events are never changed."""
        audit = self.dataset.graph(AUDIT_GRAPH)
        for triple in event:
            audit.add(triple)

    def project(self, assertion: URIRef) -> URIRef:
        """Put ``assertion`` in the graph its derived state calls for (ADR-0002).
        Returns that graph. Identity triples follow; orphans are removed."""
        target_id = (
            TRUSTED_GRAPH if self.state(assertion) == EK.Accepted else UNTRUSTED_GRAPH
        )
        target = self.dataset.graph(target_id)
        facts = self.facts(assertion)
        for graph_id in (TRUSTED_GRAPH, UNTRUSTED_GRAPH):
            if graph_id == target_id:
                continue
            other = self.dataset.graph(graph_id)
            for triple in list(other.triples((assertion, None, None))):
                other.remove(triple)
            for subject, link in (
                (facts.value(assertion, EK.aboutEmployee), EK.aboutEmployee),
                (facts.value(assertion, EK.fromSource), EK.fromSource),
            ):
                if (None, link, subject) not in other:
                    for triple in list(other.triples((subject, None, None))):
                        other.remove(triple)
        for triple in facts:
            target.add(triple)
        return target_id

    def rebuild_projection(self) -> int:
        """Recompute both trust graphs from the audit graph. Returns moves made."""
        mismatches = self.check_projection()
        for assertion in {a for a, _, _ in mismatches}:
            self.project(assertion)
        return len(mismatches)

    def check_projection(self) -> list[tuple[URIRef, URIRef | None, URIRef]]:
        """(assertion, graph it is in, state from the audit) for every mismatch."""
        trusted = self.dataset.graph(TRUSTED_GRAPH)
        untrusted = self.dataset.graph(UNTRUSTED_GRAPH)
        known = set(trusted.subjects(RDF.type, EK.FactAssertion)) | set(
            untrusted.subjects(RDF.type, EK.FactAssertion)
        )
        mismatches = []
        for assertion in sorted(known):
            state = self.state(assertion)
            expected = TRUSTED_GRAPH if state == EK.Accepted else UNTRUSTED_GRAPH
            unexpected = UNTRUSTED_GRAPH if expected == TRUSTED_GRAPH else TRUSTED_GRAPH
            if (assertion, None, None) in self.dataset.graph(unexpected):
                mismatches.append((assertion, unexpected, state))
        return mismatches

    def save(self) -> None:
        """Atomic: write a temp file beside the store, then replace it (ADR-0005)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(self.dataset.serialize(format="trig", encoding="utf-8"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # -- reading -----------------------------------------------------------

    def graph_of(self, assertion: URIRef) -> URIRef | None:
        for graph_id in (TRUSTED_GRAPH, UNTRUSTED_GRAPH):
            if (assertion, RDF.type, EK.FactAssertion) in self.dataset.graph(graph_id):
                return graph_id
        return None

    def facts(self, assertion: URIRef) -> Graph:
        """The assertion with its employee's and source's identity triples."""
        facts = Graph()
        for graph_id in (TRUSTED_GRAPH, UNTRUSTED_GRAPH):
            graph = self.dataset.graph(graph_id)
            for subject in (
                assertion,
                graph.value(assertion, EK.aboutEmployee),
                graph.value(assertion, EK.fromSource),
            ):
                if subject is not None:
                    for p, o in graph.predicate_objects(subject):
                        facts.add((subject, p, o))
        return facts

    def events(self, assertion: URIRef | None = None) -> list[URIRef]:
        """Review events, optionally for one assertion, in sequence order."""
        audit = self.dataset.graph(AUDIT_GRAPH)
        found = audit.subjects(RDF.type, EK.ReviewEvent)
        if assertion is not None:
            found = (e for e in found if (e, PROV.used, assertion) in audit)
        return sorted(found, key=lambda e: audit.value(e, EK.sequence).toPython())

    def event(self, event: URIRef) -> Graph:
        audit = self.dataset.graph(AUDIT_GRAPH)
        g = Graph()
        for p, o in audit.predicate_objects(event):
            g.add((event, p, o))
        return g

    def state(self, assertion: URIRef) -> URIRef:
        """The toState of the latest event; candidate when there is none (ADR-0002)."""
        events = self.events(assertion)
        if not events:
            return EK.Candidate
        return self.dataset.graph(AUDIT_GRAPH).value(events[-1], EK.toState)

    def next_sequence(self) -> int:
        audit = self.dataset.graph(AUDIT_GRAPH)
        return 1 + max(
            (s.toPython() for s in audit.objects(None, EK.sequence)), default=0
        )

    def accepted_conflicts(self, assertion: URIRef) -> list[URIRef]:
        """Other accepted assertions for the same employee and property whose value
        differs. Allowed, but must be flagged (ADR-0002)."""
        trusted = self.dataset.graph(TRUSTED_GRAPH)
        facts = self.facts(assertion)
        employee = facts.value(assertion, EK.aboutEmployee)
        predicate = facts.value(assertion, EK.predicate)
        value = facts.value(assertion, EK.value)
        return sorted(
            other
            for other in trusted.subjects(EK.aboutEmployee, employee)
            if other != assertion
            and trusted.value(other, EK.predicate) == predicate
            and trusted.value(other, EK.value) != value
        )

    def assertions(self):
        for graph_id in (UNTRUSTED_GRAPH, TRUSTED_GRAPH):
            graph = self.dataset.graph(graph_id)
            for assertion in graph.subjects(RDF.type, EK.FactAssertion):
                yield graph_id, assertion, graph

    def employee_ids(self) -> set[tuple[str, str]]:
        """(issuer, employee ID) of every employee in the trusted or untrusted graph."""
        ids = set()
        for graph_id in (TRUSTED_GRAPH, UNTRUSTED_GRAPH):
            graph = self.dataset.graph(graph_id)
            for employee in graph.subjects(RDF.type, EK.Employee):
                ids.add(
                    (
                        str(graph.value(employee, EK.issuer)),
                        str(graph.value(employee, EK.employeeId)),
                    )
                )
        return ids

    def _runs(self) -> list[tuple[URIRef, URIRef, Graph]]:
        """(source, run, run graph) for every completed run, oldest first.
        Incomplete runs are ignored (ADR-0003)."""
        runs = []
        for graph in self.dataset.graphs():
            if not str(graph.identifier).startswith(RUN_GRAPH_PREFIX):
                continue
            for run in graph.subjects(EK.runStatus, EK.Completed):
                started = graph.value(run, PROV.startedAtTime).toPython()
                source = graph.value(run, EK.forSource)
                runs.append((started, str(run), source, run, graph))
        return [(source, run, graph) for *_, source, run, graph in sorted(runs)]

    def completed_runs(self, source: URIRef) -> list[tuple[URIRef, Graph]]:
        """Completed runs of ``source``, oldest first."""
        return [(run, graph) for s, run, graph in self._runs() if s == source]

    def latest_runs(self) -> dict[URIRef, tuple[URIRef, Graph]]:
        """The latest completed run of each source."""
        return {source: (run, graph) for source, run, graph in self._runs()}

    def observed(self, run_graph: Graph) -> set[URIRef]:
        return set(run_graph.objects(None, EK.ofAssertion))

    def observations(self) -> dict[URIRef, list[dict]]:
        """Every observation in completed runs, by assertion, oldest run first.
        ponytail: rebuilt per call from all run graphs; cache or index when it is slow."""
        index: dict[URIRef, list[dict]] = {}
        for _, run, graph in self._runs():
            for obs in sorted(graph.subjects(RDF.type, EK.Observation)):
                observed_at = graph.value(obs, EK.observedAt)
                index.setdefault(graph.value(obs, EK.ofAssertion), []).append(
                    {
                        "run": str(run),
                        "source_reference": str(graph.value(obs, EK.sourceReference)),
                        "raw_value": str(graph.value(obs, EK.rawValue)),
                        "observed_at": observed_at and str(observed_at),
                        "validation": _local(graph.value(obs, EK.validationResult)),
                        "validation_messages": sorted(
                            str(m) for m in graph.objects(obs, EK.validationMessage)
                        ),
                    }
                )
        return index

    def quarantined(self, run_graph: Graph) -> list[dict]:
        return sorted(
            (
                {
                    "source_reference": str(run_graph.value(q, EK.sourceReference)),
                    "reason": str(run_graph.value(q, EK.quarantineReason)),
                }
                for q in run_graph.subjects(RDF.type, EK.QuarantinedRecord)
            ),
            key=lambda q: q["source_reference"],
        )


def _local(iri) -> str | None:
    return None if iri is None else str(iri).rsplit("#", 1)[-1]
