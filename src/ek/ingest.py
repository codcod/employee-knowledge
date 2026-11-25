"""Turn one adapter read into one ingestion run (ADR-0001, ADR-0003, ADR-0006)."""

import hashlib
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, XSD

from .adapters.base import ReadResult, SourceError
from .config import SourceConfig
from .constants import EK, FIELD_PREDICATES, RUN_GRAPH_PREFIX
from .graph.store import KnowledgeStore
from .identity import employee_uri, source_uri
from .validation import Finding, property_range, validate

SEP = "\x1f"  # U+001F unit separator


def digest(*parts: str) -> str:
    return hashlib.sha256(SEP.join(parts).encode("utf-8")).hexdigest()


def normalise(field: str, raw: str) -> str:
    """Trim surrounding whitespace; lowercase email addresses (architecture §13 q11)."""
    value = raw.strip()
    return value.lower() if field == "work_email" else value


def assertion_uri(
    source_id: str, record_key: str, predicate: URIRef, datatype: URIRef, value: str
) -> URIRef:
    return URIRef(
        "urn:employee-knowledge:assertion:"
        + digest(source_id, record_key, str(predicate), str(datatype), value)
    )


def _check_records(source: SourceConfig, result: ReadResult) -> None:
    """Hold every adapter to what the Excel adapter guarantees (ADR-0011). Messages
    name source references only: IDs and values are employee data."""
    mapped = set(source.mapping) - {"employee_id"}  # ontology first
    seen: dict[str, str] = {}
    for r in result.records:
        ref = r.source_reference
        key = r.employee_id
        if not isinstance(key, str) or not key or key != key.strip():
            raise SourceError(f"adapter returned an unusable employee ID at {ref}")
        if key in seen:  # the source would contradict itself; Excel quarantines these
            raise SourceError(
                f"adapter returned the same employee ID at {seen[key]} and {ref}"
            )
        seen[key] = ref
        if extra := set(r.values) - mapped:
            raise SourceError(f"adapter returned unmapped fields {sorted(extra)}")
        if not all(isinstance(v, str) for v in r.values.values()):
            raise SourceError(f"adapter returned a value that is not text at {ref}")


class IngestError(RuntimeError):
    """The run produced structurally invalid records (a bug). Nothing was stored."""

    def __init__(self, findings: list[Finding]):
        self.findings = findings
        super().__init__(f"Ingestion aborted: {len(findings)} model finding(s)")


@dataclass(frozen=True)
class IngestSummary:
    run: URIRef
    observations: int
    assertions: int
    new_assertions: int
    quarantined: int
    value_violations: int


def ingest(
    store: KnowledgeStore,
    source: SourceConfig,
    result: ReadResult,
    started_at: datetime,
) -> IngestSummary:
    """Add one run to ``store`` in memory. The caller saves; on error nothing changes."""
    _check_records(source, result)
    run_id = uuid.uuid4()
    run = URIRef(f"urn:employee-knowledge:run:{run_id}")
    src = source_uri(source.id)
    file = URIRef(f"urn:employee-knowledge:file:{result.sha256}")
    g, facts = Graph(), Graph()  # run graph; assertions with their employees

    g.add((src, RDF.type, EK.Source))
    for t in (EK.IngestionRun, PROV.Activity):
        g.add((run, RDF.type, t))
    g.add((run, EK.forSource, src))
    g.add((run, EK.mappingVersion, Literal(source.mapping_version)))
    g.add((run, PROV.used, file))
    g.add((run, PROV.startedAtTime, Literal(started_at, datatype=XSD.dateTime)))
    g.add((file, RDF.type, PROV.Entity))
    g.add((file, EK.fileName, Literal(result.file_name)))
    g.add((file, EK.sha256, Literal(result.sha256)))

    observations: dict[URIRef, list[URIRef]] = defaultdict(list)
    facts.add((src, RDF.type, EK.Source))
    for record in result.records:
        employee = employee_uri(source.issuer, record.employee_id)
        facts.add((employee, RDF.type, EK.Employee))
        facts.add((employee, EK.employeeId, Literal(record.employee_id)))
        facts.add((employee, EK.issuer, Literal(source.issuer)))
        for field, raw in record.values.items():
            value = normalise(field, raw)
            if not value:
                continue
            predicate = FIELD_PREDICATES[field]
            datatype = property_range(predicate)
            assertion = assertion_uri(
                source.id, record.employee_id, predicate, datatype, value
            )
            for t in (EK.FactAssertion, PROV.Entity):
                facts.add((assertion, RDF.type, t))
            facts.add((assertion, EK.aboutEmployee, employee))
            facts.add((assertion, EK.predicate, predicate))
            facts.add((assertion, EK.value, Literal(value, datatype=datatype)))
            facts.add((assertion, EK.fromSource, src))

            obs = URIRef(
                "urn:employee-knowledge:observation:"
                + digest(str(run), str(assertion), record.source_reference)
            )
            for t in (EK.Observation, PROV.Entity):
                g.add((obs, RDF.type, t))
            g.add((obs, EK.ofAssertion, assertion))
            g.add((obs, PROV.wasGeneratedBy, run))
            g.add((obs, EK.sourceRecordKey, Literal(record.employee_id)))
            g.add((obs, EK.sourceReference, Literal(record.source_reference)))
            g.add((obs, EK.rawValue, Literal(raw)))
            if record.observed_at:  # only when the source supplies it, never defaulted
                g.add(
                    (
                        obs,
                        EK.observedAt,
                        Literal(record.observed_at, datatype=XSD.dateTime),
                    )
                )
            observations[assertion].append(obs)

    for q in result.quarantined:
        qr = URIRef(
            "urn:employee-knowledge:quarantine:" + digest(str(run), q.source_reference)
        )
        for t in (EK.QuarantinedRecord, PROV.Entity):
            g.add((qr, RDF.type, t))
        g.add((qr, PROV.wasGeneratedBy, run))
        g.add((qr, EK.sourceReference, Literal(q.source_reference)))
        g.add((qr, EK.quarantineReason, Literal(q.reason)))

    findings = validate(g + facts)
    if model := [f for f in findings if f.kind == "model"]:
        raise IngestError(model)
    messages: dict[URIRef, list[str]] = defaultdict(list)
    for f in findings:
        messages[URIRef(f.focus)].append(f.message)
    violations = 0
    for assertion, obs_list in observations.items():
        for obs in obs_list:
            if assertion in messages:
                violations += 1
                g.add((obs, EK.validationResult, EK.Violation))
                for m in messages[assertion]:
                    g.add((obs, EK.validationMessage, Literal(m)))
            else:
                g.add((obs, EK.validationResult, EK.Conforms))

    g.add((run, PROV.endedAtTime, Literal(datetime.now(UTC), datatype=XSD.dateTime)))
    g.add((run, EK.runStatus, EK.Completed))  # last (ADR-0003)
    new = store.add_run(URIRef(f"{RUN_GRAPH_PREFIX}{run_id}"), g, facts)
    return IngestSummary(
        run=run,
        observations=sum(len(o) for o in observations.values()),
        assertions=len(observations),
        new_assertions=new,
        quarantined=len(result.quarantined),
        value_violations=violations,
    )
