# ADR-0001: Assertion model

- **Status:** Accepted (2026-11-17)
- **Supersedes:** ADR-001 (one-line entry)
- **Related:** ADR-0002, ADR-0003, ADR-0006

## Context

Every fact is a claim by one source (architecture §3.1, §5.2). The same value from two
sources must stay two claims, and each claim needs provenance and a trust state. Plain
RDF triples (`employee ek:department "Engineering"`) cannot tell two sources asserting the
same value apart, and they give provenance nowhere to attach.

Until now, the code used an undefined `ek:FactAssertion` resource and stored ingestion
time as observation time. The SHACL shapes targeted properties on `ek:Employee` that the
code never writes.

## Decision

Represent each claim as an `ek:FactAssertion` resource that also has type `prov:Entity`.
An assertion is immutable: it describes *what* was claimed, never *when* or *how
often*.

```turtle
<urn:employee-knowledge:assertion:{sha256}> a ek:FactAssertion, prov:Entity ;
    ek:aboutEmployee <urn:employee-knowledge:employee:{issuer}:{id}> ;
    ek:predicate     ek:department ;                 # an ek:AssertableProperty
    ek:value         "Engineering"^^xsd:string ;     # typed by the property's rdfs:range
    ek:fromSource    <urn:employee-knowledge:source:{source-id}> .
```

- Value properties (`ek:fullName`, `ek:department`, …) have type `ek:AssertableProperty`.
  They are used as objects of `ek:predicate`, never as triple predicates on an employee.
  They have no `rdfs:domain`.
- The value's datatype comes from the property's `rdfs:range`. Every current property is
  `xsd:string`.
- The employee resource carries only identity: `a ek:Employee ; ek:employeeId ; ek:issuer`
  (ADR-0004). It is written into each graph that holds one of its assertions, so that
  graph can be queried on its own.
- Provenance is attached through `ek:Observation` resources, which use PROV-O
  (`prov:wasGeneratedBy` the ingestion run). Observations live in run graphs (ADR-0003).
- Review decisions are `ek:ReviewEvent` resources of type `prov:Activity`, stored in the
  audit graph (ADR-0002).
- Every class and property named here is defined in `ontology/employees.ttl`.

URI patterns:

| Resource | URI |
|---|---|
| Assertion | `urn:employee-knowledge:assertion:{sha256}` (ADR-0003) |
| Employee | `urn:employee-knowledge:employee:{issuer}:{id}` (ADR-0004) |
| Source | `urn:employee-knowledge:source:{source-id}` |
| Ingestion run | `urn:employee-knowledge:run:{uuid}` |
| Observation | `urn:employee-knowledge:observation:{sha256}` |
| Review event | `urn:employee-knowledge:review:{uuid}` |

## Alternatives considered

- **Plain triples on the employee.** Cannot distinguish sources or carry provenance.
  Rejected.
- **RDF-star / RDF 1.2 triple terms.** Semantically cleaner, but RDFLib support is partial
  and SHACL tooling is immature. Reconsider when both mature.
- **One named graph per assertion.** Works with standard RDF, but it would use up graph
  names, which the trust model needs for untrusted/trusted/audit/run separation.
- **Full PROV-O qualified patterns for everything.** More verbose and adds nothing for
  current needs. PROV-O is used where it fits (entities, activities, generation).

## Consequences

- Queries go through `ek:predicate`/`ek:value` rather than direct properties. A
  convenience view for consumers can be projected later (architecture §4.8).
- Assertions carry no mutable fields. Timestamps and validation live on observations,
  and status on review events.
- SHACL must validate assertions and observations, not the employee node (ADR-0006).
- `ek:reviewStatus`, `ek:observedAt` on the assertion, `ek:sourceId`,
  `ek:sourceRecordId` and `ek:sourceReference` on the assertion are removed.

## Migration

Only synthetic local stores exist. Delete them and re-ingest; no conversion is
provided.
