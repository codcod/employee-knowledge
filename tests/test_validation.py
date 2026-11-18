"""SHACL shapes and the validator (ADR-0006), on synthetic graphs in the ADR-0001/3 model."""

from importlib.resources import files

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, PROV, RDF, XSD

from ek.constants import EK
from ek.validation import validate

VALID = """
@prefix ek: <https://w3id.org/employee-knowledge/ontology#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<urn:employee-knowledge:employee:example-hr:E-1> a ek:Employee ;
    ek:employeeId "E-1" ; ek:issuer "example-hr" .

<urn:employee-knowledge:source:hr> a ek:Source .

<urn:employee-knowledge:assertion:a1> a ek:FactAssertion, prov:Entity ;
    ek:aboutEmployee <urn:employee-knowledge:employee:example-hr:E-1> ;
    ek:predicate ek:department ;
    ek:value "Engineering" ;
    ek:fromSource <urn:employee-knowledge:source:hr> .

<urn:employee-knowledge:run:r1> a ek:IngestionRun, prov:Activity ;
    ek:forSource <urn:employee-knowledge:source:hr> ;
    ek:mappingVersion "1" ;
    prov:used <urn:employee-knowledge:file:f1> ;
    prov:startedAtTime "2026-01-01T00:00:00Z"^^xsd:dateTime ;
    ek:runStatus ek:Completed .

<urn:employee-knowledge:file:f1> a prov:Entity ;
    ek:fileName "employees.xlsx" ;
    ek:sha256 "0000000000000000000000000000000000000000000000000000000000000000" .

<urn:employee-knowledge:observation:o1> a ek:Observation, prov:Entity ;
    ek:ofAssertion <urn:employee-knowledge:assertion:a1> ;
    prov:wasGeneratedBy <urn:employee-knowledge:run:r1> ;
    ek:sourceRecordKey "E-1" ;
    ek:sourceReference "employees.xlsx#Employees!2" ;
    ek:rawValue " Engineering " .

<urn:employee-knowledge:quarantine:q1> a ek:QuarantinedRecord ;
    prov:wasGeneratedBy <urn:employee-knowledge:run:r1> ;
    ek:sourceReference "employees.xlsx#Employees!7" ;
    ek:quarantineReason "missing employee ID" .

<urn:employee-knowledge:review:e1> a ek:ReviewEvent, prov:Activity ;
    prov:used <urn:employee-knowledge:assertion:a1> ;
    ek:reviewAction ek:Accept ;
    ek:fromState ek:Candidate ;
    ek:toState ek:Accepted ;
    ek:reviewer "reviewer-1" ;
    ek:reviewReason "Checked against synthetic HR" ;
    ek:policyVersion "none" ;
    ek:sequence 1 ;
    prov:endedAtTime "2026-01-02T00:00:00Z"^^xsd:dateTime .
"""

EMPLOYEE = URIRef("urn:employee-knowledge:employee:example-hr:E-1")
ASSERTION = URIRef("urn:employee-knowledge:assertion:a1")
OBSERVATION = URIRef("urn:employee-knowledge:observation:o1")
RUN = URIRef("urn:employee-knowledge:run:r1")
FILE = URIRef("urn:employee-knowledge:file:f1")
EVENT = URIRef("urn:employee-knowledge:review:e1")


def graph() -> Graph:
    return Graph().parse(data=VALID, format="turtle")


def test_valid_graph_has_no_findings():
    assert validate(graph()) == []


@pytest.mark.parametrize(
    ("subject", "predicate", "path"),
    [
        (EMPLOYEE, EK.employeeId, EK.employeeId),
        (EMPLOYEE, EK.issuer, EK.issuer),
        (ASSERTION, EK.aboutEmployee, EK.aboutEmployee),
        (ASSERTION, EK.fromSource, EK.fromSource),
        (OBSERVATION, EK.sourceReference, EK.sourceReference),
        (OBSERVATION, PROV.wasGeneratedBy, PROV.wasGeneratedBy),
        (OBSERVATION, EK.rawValue, EK.rawValue),
        (RUN, EK.mappingVersion, EK.mappingVersion),
        (RUN, PROV.startedAtTime, PROV.startedAtTime),
        (EVENT, EK.reviewReason, EK.reviewReason),
        (EVENT, EK.sequence, EK.sequence),
    ],
)
def test_missing_required_field_is_a_model_finding(subject, predicate, path):
    g = graph()
    g.remove((subject, predicate, None))
    findings = validate(g)
    assert [(f.kind, f.focus, f.path) for f in findings] == [
        ("model", str(subject), str(path))
    ]


@pytest.mark.parametrize(
    ("subject", "predicate", "bad"),
    [
        (EVENT, EK.reviewer, Literal("   ")),
        (EVENT, EK.reviewReason, Literal("")),
        (OBSERVATION, EK.observedAt, Literal("yesterday")),
        (FILE, EK.sha256, Literal("not-a-hash")),
        (EVENT, EK.reviewAction, EK.Accepted),
    ],
)
def test_malformed_field_is_a_model_finding(subject, predicate, bad):
    g = graph()
    g.set((subject, predicate, bad))
    findings = validate(g)
    # Nested shapes (sh:node) may report both the parent and the detail.
    assert findings
    assert {f.kind for f in findings} == {"model"}


def test_predicate_must_be_an_assertable_property():
    g = graph()
    g.set((ASSERTION, EK.predicate, EK.employeeId))
    kinds = {(f.kind, f.path) for f in validate(g)}
    assert ("model", str(EK.predicate)) in kinds


@pytest.mark.parametrize(
    "bad",
    [
        Literal(42),
        Literal("2026-01-01", datatype=XSD.date),
        Literal(""),
        Literal("   "),
        URIRef("urn:not-a-literal"),
    ],
)
def test_bad_value_is_a_value_finding_naming_the_property(bad):
    g = graph()
    g.set((ASSERTION, EK.value, bad))
    value_findings = [f for f in validate(g) if f.kind == "value"]
    assert len(value_findings) == 1
    assert value_findings[0].focus == str(ASSERTION)
    assert str(EK.department) in value_findings[0].message


def test_conflicting_assertions_are_structurally_valid():
    """Validation is not reconciliation: two sources disagreeing is not a finding."""
    g = graph()
    other = URIRef("urn:employee-knowledge:assertion:a2")
    for p, o in g.predicate_objects(ASSERTION):
        g.add((other, p, o))
    g.set((other, EK.value, Literal("Product")))
    assert validate(g) == []


def test_code_namespace_matches_the_ontology():
    """EK-013: the EK constant and the ontology IRI must not drift apart."""
    ttl = (files("ek") / "ontology" / "employees.ttl").read_text(encoding="utf-8")
    ontologies = set(
        Graph().parse(data=ttl, format="turtle").subjects(RDF.type, OWL.Ontology)
    )
    assert ontologies == {URIRef(str(EK).rstrip("#"))}
    assert str(EK).startswith("https://w3id.org/employee-knowledge/")
