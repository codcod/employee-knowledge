# Architecture decisions

One file per decision: `NNNN-short-title.md`. Each ADR covers context, decision,
alternatives considered, consequences and migration implications.

Status values:

- **Accepted:** decided by the project owner.
- **Proposed:** written and approved as part of a plan, but not decided on its own.
- **Provisional:** depends on an open question in architecture §13.
- **Superseded:** replaced by a later ADR.

## Index

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-assertion-model.md) | Accepted | Each claim is an immutable `ek:FactAssertion` with PROV-O provenance. |
| [0002](0002-trust-derived-from-audit.md) | Accepted | Review events in the audit graph are the only record of trust; untrusted/trusted membership is a projection of them. |
| [0003](0003-assertion-identity-and-observations.md) | Accepted | Assertion ID = source + record key + predicate + typed value. Each ingestion run has its own graph of observations. |
| [0004](0004-employee-identity.md) | Accepted | The employee URI includes the ID issuer; no automatic merging across issuers. |
| [0005](0005-storage.md) | Accepted | RDFLib `Dataset` + TriG with atomic save; RDF kept over a relational log. |
| [0006](0006-validation.md) | Accepted | SHACL model shapes per class and value shapes per property. Data violations are recorded; model violations abort. |
| [0007](0007-source-config.md) | Accepted | Source configuration in TOML via `tomllib`; unknown keys are an error. |
| [0008](0008-value-normalisation.md) | Accepted | Trim surrounding whitespace; lowercase `work_email`; compare exactly. |
| [0009](0009-ontology-namespace.md) | Accepted | The ontology namespace is `https://w3id.org/employee-knowledge/ontology#`; instance URNs are unchanged. |
| [0010](0010-authority-policy.md) | Proposed | A versioned TOML policy per property; it recommends, never decides, and never waives review. Review events record the version in force. |

### Superseded one-line entries

These are kept for history.

| ID | Superseded by | Original text |
|---|---|---|
| ADR-001 | 0001 | Retain each fact as a provenance-bearing assertion; never overwrite source facts during ingestion. |
| ADR-002 | 0002 | All ingestion starts untrusted; promotion is explicit and audited. |
| ADR-003 | 0004 | The organisation-issued employee ID is the primary key. Names are not unique identifiers. |
| ADR-004 | 0005 | RDFLib + TriG for the portable prototype; reassess before production. |
