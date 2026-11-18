# Employee Knowledge — Architecture

**Status:** Accepted (2026-11-18). Normative; changed only through ADRs. 
**Scope:** Initial employee-data knowledge platform, beginning with Excel and designed
for additional enterprise sources 
**Audience:** Engineers and coding agents implementing the project

## 1. Purpose and outcomes

Employee Knowledge creates a governed, queryable view of employee information gathered
from multiple systems: Excel workbooks, Confluence, Jira, Power BI and later sources.
These systems may contain overlapping, stale, incomplete or contradictory employee
attributes.

The platform must:

1. Ingest employee-related information from heterogeneous sources.
2. map source records and fields to a manually defined employee ontology;
3. preserve the original source, record, version and observation context for every fact;
4. reconcile identities without treating names as unique identifiers;
5. retain conflicting assertions instead of silently overwriting them;
6. distinguish unreviewed facts from facts accepted under an explicit trust policy;
7. surface discrepancies with enough evidence for a human to resolve them;
8. provide a safe, controlled query interface, including AI-assisted
   natural-language-to-SPARQL in a later phase; and
9. make every trust decision explainable and auditable.

The result is not simply a merged employee spreadsheet. It is a provenance-aware
knowledge graph in which a consumer can ask both “what do we currently believe?” and
“why do we believe it?”

## 2. Non-goals and boundaries

The first release is a local, testable vertical slice, not a complete enterprise
deployment.

Out of scope for the first slice:

- live production access to Confluence, Jira or Power BI;
- automatic write-back to any source system;
- autonomous AI decisions that promote facts to trusted status;
- unrestricted SPARQL execution by users or language models;
- a universal ranking that declares one source authoritative for every employee
  attribute;
- a full enterprise identity-management or master-data-management replacement;
- production hosting, SSO, enterprise RBAC, high availability and operational SLAs
  (the prototype's reviewer argument is a non-empty local label, not authorisation; see
  §4.7);
- committing real employee records, credentials or production graph stores to Git.

Pickle is the development workflow and ticket-governance layer. It is not the
runtime, data store, ingestion engine or ontology framework. Jira may later be an
employee-data source; that is separate from Pickle's own project board.

## 3. Core architectural principles

### 3.1 Assertions, not destructive field updates

Do not ingest a source row by overwriting properties on a single employee record.
Represent each observed value as an independent assertion. Two sources claiming
different departments for the same employee must coexist until reconciled.

An assertion should identify:

- the employee it is about;
- the ontology predicate/property;
- the observed value and datatype;
- the source system and source instance;
- a stable source-record identifier;
- a source reference such as workbook/sheet/row, Confluence page/version, Jira
  issue/user, or Power BI workspace/dataset/refresh;
- observation and ingestion timestamps;
- the ingestion run and mapping version;
- validation and review state; and
- any reviewer, decision, reason and decision timestamp.

### 3.2 Provenance is first-class

Every fact must be traceable to evidence. Do not accept an AI-extracted fact unless the
system can retain a source reference and, where applicable, a quoted span, cell
coordinate, field name or API object identifier.

Keep source provenance separate from trust. A source may be authoritative for one
property and merely suggestive for another. A workbook or connector must not be globally
marked trusted in a way that silently trusts every fact it contains.

### 3.3 Trust is explicit and assertion-level

All new assertions enter the untrusted graph. A fact can be promoted only through an
explicit review operation that checks policy and records who approved it and why.
Promotion is not the same as validation: a syntactically valid value can still be
factually wrong.

The initial implementation uses human-controlled promotion. Later AI or policy services
may recommend decisions, assemble evidence and prioritise review, but they must not
autonomously promote facts.

### 3.4 Separate quality dimensions

Do not collapse all quality into a single trusted/untrusted flag. Keep these concepts
distinct:

- **Structural validity:** Is the record well-formed and does it satisfy the
  ontology/SHACL constraints?
- **Identity confidence:** Are we confident that the source record refers to this
  employee?
- **Factual reliability:** Is there sufficient evidence that the value is correct and
  current?
- **Trust/review status:** Has an authorised process accepted this particular assertion
  for trusted use?
- **Freshness:** Is the assertion recent enough for the property-specific policy?

A fact can be structurally valid but unverified, trusted but stale, or high-confidence
but still awaiting approval.

### 3.5 AI assists; policy and people decide

AI may suggest Excel column mappings, extract candidate facts from documents, identify
likely identity matches, compare conflicting values, explain discrepancies and draft
review recommendations. AI output must be treated as a proposal.

AI must never:
- fabricate a source reference or evidence;
- suppress a conflicting assertion;
- silently choose a winner and discard alternatives;
- change trust status without an authorised review action;
- execute arbitrary write operations against source systems; or
- receive unrestricted graph-store credentials.

## 4. Logical components

The system is organised into the following components. They may begin as modules in one
Python package; do not introduce microservices before scale or operational needs justify
them.

### 4.1 Source adapters

Each adapter is read-only and converts its source into a common internal record format.
An adapter is responsible for source-specific pagination, version handling, extraction
and stable source-record references, but not for deciding trust.

Initial and planned adapters:

| Source | Initial status | Provenance to preserve |
|---|---|---|
| Excel workbooks | First implementation | File identity/hash, sheet, row, headers, ingestion run, optional workbook version/date |
| Confluence | Planned | Space, page ID, page version, URL, extraction timestamp, content location |
| Jira | Planned | Site/project, issue or user identifier, field, issue/user update time |
| Power BI | Planned | Tenant/workspace, dataset/report, refresh timestamp, table/column/row key where available |
| Other systems | Extension point | Stable source object ID, source version and evidence reference |

Do not assume that every source has a unique employee ID. If it does not, its records
must go through identity resolution with an explicit confidence and review outcome.

### 4.2 Normalisation and mapping

Map source-specific column names and field shapes to ontology properties using versioned
mapping configuration. Keep the original source value and enough metadata to reproduce
the mapping.

Mappings should be explicit and inspectable. AI may propose mappings, but a mapping
should be approved and versioned before it is used for production ingestion.

Handle nulls, blank strings, formatting differences, date/time zones, case normalisation
and controlled vocabularies deliberately. Do not treat an absent value as a deletion
unless a source-specific contract says that absence means deletion.

### 4.3 Identity resolution

The canonical employee identity should be based on a stable, organisation-issued
employee identifier where available. Names, job titles, departments and email addresses
are not guaranteed unique or immutable and must not independently be treated as primary
keys.

Identity resolution should:
- preserve source identifiers and aliases;
- distinguish deterministic matches from probabilistic candidates;
- record match rationale, confidence and evidence;
- support unresolved and ambiguous records without forcing a merge;
- avoid merging two people solely because their names match; and
- make corrections and merge/split decisions auditable.

The first slice may require an employee ID column and reject or quarantine rows without
it. Cross-source fuzzy matching is later work.

### 4.4 Ontology and validation

The ontology is manually curated and version-controlled. It defines the classes and
properties the platform understands, their domains/ranges, labels, definitions and,
where appropriate, controlled values.

The initial ontology should cover at least:
- Employee;
- stable employee identifier;
- full/display name;
- work email;
- department or organisational unit;
- job title;
- manager relationship or manager employee identifier;
- work location; and
- employment status.

Use OWL/RDFS for vocabulary and semantic relationships. Use SHACL for operational data
constraints such as required fields, cardinality, datatypes, formats and controlled
values. OWL reasoning is not a substitute for validation rules.

How shapes are applied to the assertion model, and how violations are handled:
[ADR-0006](decisions/0006-validation.md).

Every ingestion run should be able to report structural validation failures separately
from factual discrepancies and trust decisions.

### 4.5 Assertion and graph storage

Use RDF as the canonical representation. The prototype can use RDFLib and TriG files for
portability and local development. Keep graph access behind a repository/store interface
so the storage engine can later move to a managed graph database without rewriting
adapters and business logic.

Use named graphs to separate concerns:

- `urn:employee-knowledge:graph:untrusted` — assertions ingested but not yet accepted;
- `urn:employee-knowledge:graph:trusted` — assertions accepted by the review policy;
- `urn:employee-knowledge:graph:audit` — review actions, promotions, corrections and
  other governance events;
- source- or run-specific graphs may be added for staging, snapshots or reproducibility.
  Each ingestion run writes its provenance to `urn:employee-knowledge:graph:run:{uuid}`
  ([ADR-0003](decisions/0003-assertion-identity-and-observations.md)).

Graph membership of untrusted and trusted assertions is a projection of the review events
in the audit graph, which are the only record of trust state
([ADR-0002](decisions/0002-trust-derived-from-audit.md)). Storage choices:
[ADR-0005](decisions/0005-storage.md).

The exact storage model should preserve assertion identity and provenance. A recommended
pattern is to represent each assertion as a resource linked to the employee, predicate,
value and provenance metadata. Do not rely on bare RDF triples alone if doing so loses
the ability to distinguish two sources asserting the same value.

A trusted view is a projection over accepted assertions, not a destructive merge. If
multiple trusted assertions still conflict, the system must surface that conflict and
apply only a documented, property-specific resolution policy. It must not choose
arbitrarily.

### 4.6 Reconciliation and discrepancy detection

Reconciliation compares assertions that refer to the same employee and property. The
initial discrepancy report should show:

- employee identity;
- property;
- each distinct observed value;
- source and source record/reference;
- observed/ingested timestamps;
- validation and trust state; and
- any existing review decision.

Initial discrepancy categories:
- conflicting values for the same employee/property;
- duplicate or ambiguous employee identities;
- missing required attributes;
- stale assertions beyond property-specific freshness limits;
- SHACL/ontology validation failures;
- broken manager references;
- source records that cannot be mapped or resolved confidently; and
- unexpected changes between source versions or ingestion runs.

Do not label every difference as an error. Some values may legitimately vary over time.
The reconciliation layer must distinguish current-state conflicts from historical
changes when effective dates or source versions are available.

### 4.7 Review and promotion workflow

A review item should present the competing assertions and direct evidence references. A
reviewer should be able to accept an assertion, reject it, mark it superseded, request
more evidence or leave it unresolved. The states and allowed transitions, including
revoking, reopening and restoring, are defined in
[ADR-0002](decisions/0002-trust-derived-from-audit.md).

Promotion must:
1. verify the assertion exists and is currently untrusted;
2. verify the reviewer is authorised. The local prototype only requires a non-empty
   reviewer argument; that is a label, not authentication or authorisation. Production
   must enforce identity and role;
3. require a non-empty reason and, where policy requires it, supporting evidence;
4. move or reclassify the assertion into the trusted graph without losing its assertion
   URI or provenance;
5. record a durable audit event containing the assertion, reviewer, reason, timestamp
   and policy/version used; and
6. leave other assertions intact so discrepancies remain explainable.

Rejection and supersession should also be auditable. Never delete the original source
evidence merely because an assertion was rejected.

### 4.8 Query and application interface

Provide a read-only query service over the graph. For the prototype, the CLI and
internal Python API are sufficient. Later, expose supported business questions through
named query templates or a constrained API.

Natural-language-to-SPARQL is a planned capability, not a prerequisite for the first
Excel slice. When added:
- generate queries only against the published ontology/schema;
- permit read-only query forms only;
- use an allow-list or validated query AST;
- apply query timeouts, row/result limits and cost limits;
- never expose arbitrary update operations;
- explain which graphs and trust statuses were queried;
- distinguish trusted-only answers from answers that include untrusted candidates; and
- include provenance/citations for returned facts.

An AI-generated answer must state when the graph has conflicting, stale, missing or
untrusted evidence rather than presenting a single unsupported value.

## 5. Data model

The model has four important entities. Their RDF representation is defined in
[ADR-0001](decisions/0001-assertion-model.md) (assertions),
[ADR-0003](decisions/0003-assertion-identity-and-observations.md) (identity, observations
and runs), [ADR-0004](decisions/0004-employee-identity.md) (employees) and
[ADR-0002](decisions/0002-trust-derived-from-audit.md) (review events).

### 5.1 Employee

A canonical employee resource identified by a stable internal employee ID. The employee
resource is the subject that assertions refer to. Avoid putting unnecessary personal
data directly on the canonical resource; the assertion model is the record of what each
source claims.

### 5.2 Fact assertion

An assertion represents one source's observation of one property value for one employee.
The following must be reachable from it at minimum. ADR-0001 keeps the assertion
immutable: timestamps, run, mapping version and validation live on its observations, and
review state on its review events.

- assertion URI/ID;
- employee URI/ID;
- ontology predicate;
- value and datatype;
- source ID;
- source record ID/reference;
- source version or snapshot identifier, when available;
- observed-at and ingested-at timestamps;
- ingestion-run ID;
- mapping/configuration version;
- validation result;
- review/trust state; and
- optional effective-from/effective-to dates where the source supplies them.

Assertion IDs must be deterministic or otherwise stable enough to support idempotent
re-ingestion. Re-ingesting an unchanged source record should not create uncontrolled
duplicates. If the source record changes, retain the new observation and the historical
context rather than overwriting evidence.

### 5.3 Source

A source describes a system, workbook family, connector or dataset. Store metadata such
as source owner, source type, configured authority by property, refresh cadence, access
classification and connector configuration version. Do not store secrets in the source
metadata or repository.

### 5.4 Review/audit event

A review event records a decision about an assertion or identity match. It includes
actor, action, reason, timestamp, relevant policy version and links to the affected
assertion(s). Audit history is append-only from the application's point of view.

## 6. Trust and source-authority policy

There is no universal “trusted source” switch. Source authority is property-specific and
should be agreed with data owners. For example, the HR system may be authoritative for
employment status, while a managed directory may be authoritative for a display name. A
Power BI report may be a derived view and not the originating authority for a field.

Define a policy matrix before automating resolution. A policy row should identify:
- ontology property;
- authoritative source(s);
- acceptable secondary sources;
- freshness window;
- whether human review is always required;
- conflict-resolution rule;
- permitted reviewer role; and
- effective date/version of the policy.

Until a policy is approved, ingest into untrusted and report the conflict. Source
precedence must never be inferred from file names, row order, last-modified timestamps
alone or an LLM's confidence.

## 7. Ingestion lifecycle

A normal ingestion run should follow this sequence:

1. **Discover/read:** retrieve source records read-only and capture source
version/snapshot metadata.
2. **Normalise:** convert source rows/objects into the common record shape without
discarding original values.
3. **Map:** apply a versioned source-to-ontology mapping.
4. **Resolve identity:** match to a canonical employee or quarantine as
unresolved/ambiguous.
5. **Create assertions:** write each observed property as a provenance-bearing assertion
in staging/untrusted storage.
6. **Validate:** run syntax, mapping, datatype and SHACL checks; keep failures visible.
7. **Reconcile:** compare with existing assertions and prior snapshots.
8. **Report:** produce ingestion summary, validation findings, unresolved identities and
discrepancies.
9. **Review:** authorised users inspect evidence and decide which assertions, if any,
can be trusted.
10. **Publish:** trusted assertions become available to trusted-only query consumers;
all history remains auditable.

The ingestion pipeline should be idempotent, observable and restartable. A failed run
must not leave a partially published trusted state.

## 8. Security, privacy and governance

Employee data is sensitive personal data. Build privacy controls into the design from
the start.

- Use least-privilege, read-only service accounts for source connectors.
- Keep secrets in a secret manager or local environment; never commit them.
- Do not commit real employee data, production workbooks, graph files, logs or generated
  reports.
- Restrict graph-store and report access by role in production.
- Encrypt data in transit and at rest in production.
- Define a lawful purpose and data minimisation rules for every ingested attribute.
- Define retention, correction, deletion and source-offboarding procedures.
- Keep access and trust-decision audit trails.
- Avoid collecting sensitive attributes unless there is a documented business and legal
  need.
- Ensure test fixtures use synthetic people and non-routable example email domains.
- Apply data classification and retention rules to AI prompts and model-provider use; do
  not send employee data to an external model without explicit approval and appropriate
  contractual/security controls.

A production implementation needs an access-control design before real data is
connected. A local prototype's reviewer string is not an authentication mechanism.

## 9. Technology choices

Initial prototype:
- Python 3.11+;
- RDFLib for RDF dataset and named-graph operations;
- TriG for local persistence;
- OWL/RDFS Turtle files for the ontology;
- SHACL with pySHACL for structural validation;
- openpyxl for Excel ingestion;
- Typer/Rich for a developer-facing CLI;
- pytest and Ruff for tests and linting.

These are pragmatic prototype choices, not an irreversible production commitment. Hide
graph persistence behind an interface. Evaluate a managed graph store,
authentication/authorisation, backups, monitoring and operational costs before
production deployment.

## 10. Repository structure

Current structure. Planned additions are marked.

```text
employee-knowledge/
├── README.md
├── AGENTS.md                  # rules for coding agents
├── pyproject.toml, uv.lock
├── .github/workflows/ci.yml   # lint and tests (GitHub Actions)
├── docs/                      # the product and how to operate it; no links to development/
│   ├── trust-model.md
│   ├── operating.md
│   └── source-onboarding.md
├── development/               # how it is built
│   ├── architecture.md        # this document (normative)
│   ├── roadmap.md             # milestones and task backlog
│   └── decisions/             # one ADR per file
├── examples/                  # synthetic data only
│   ├── README.md
│   ├── employees.xlsx
│   ├── employees-directory.xlsx
│   └── sources.toml
├── src/ek/
│   ├── adapters/
│   │   ├── base.py
│   │   ├── excel.py
│   │   └── connectors.py      # disabled Confluence/Jira/Power BI placeholders
│   ├── config.py              # sources.toml loader (ADR-0007)
│   ├── graph/store.py
│   ├── ontology/              # employees.ttl, shapes.ttl (package data)
│   ├── identity.py
│   ├── ingest.py
│   ├── reconcile.py
│   ├── review.py              # review actions and state machine (ADR-0002)
│   ├── validation.py          # SHACL validator (ADR-0006)
│   └── cli.py
└── tests/
```

Eventual target, once a module outgrows a single file: subpackages under `src/ek/` for
`identity`, `mapping`, `validation`, `reconciliation`, `review`, `query` and
`provenance`, one adapter module per source, and `tests/unit`, `tests/integration` and
`tests/fixtures`.

Move towards the target incrementally, through tasks. Do not reorganise the package for
aesthetics before the first vertical slice works.

## 11. First implementation milestone

The first milestone should prove the whole lifecycle with one Excel source and synthetic
data:

1. Load an Excel workbook with a configured sheet and column mapping.
2. Require a stable employee ID for the initial deterministic identity path.
3. Convert each non-empty mapped field to an assertion with source/sheet/row provenance.
4. Persist assertions in the untrusted named graph.
5. Validate the data against the initial ontology/SHACL shapes.
6. Ingest a second synthetic source containing at least one deliberately conflicting value.
7. Generate a discrepancy report that shows both values and their source references.
8. Promote one selected assertion through an explicit CLI/API action.
9. Verify the assertion moves to the trusted graph and an audit event is recorded.
10. Verify the competing assertion remains present and the history is not destroyed.
11. Verify re-ingestion is idempotent or document the exact versioning behaviour.
12. Verify no real data, credentials or local store files are committed.

Acceptance means a developer can reproduce the flow locally from the README using only
the synthetic fixtures and can explain the provenance and trust state of every reported
fact.

## 12. Task backlog

The milestones, the Task-001 to Task-018 backlog and the task order are kept in
[roadmap.md](roadmap.md). Open tasks are tracked as Pickle tickets (`EK-NNN`) on
`tickets/BOARD.md`.

## 13. Open questions for the project owner

The first tasks should resolve, not silently assume, these questions. Answered questions
keep their decision inline.

1. Which system issues the canonical employee ID, and does it remain stable across
   rehire or legal-entity changes? *Decided (2026-11-18):* the HR system issues it. Stability
   across rehire is still to be confirmed with the data owner.
2. Which employee attributes are in the initial business scope, and which are explicitly
   excluded?
3. Which system owns each attribute (for example, employment status, department,
   manager, location and display name)? *Decided (2026-11-18):* no source is authoritative until
   a versioned policy exists (Task-012); every fact needs a review.
4. Are historical values needed, and do sources provide effective dates or only
   last-modified timestamps? *Decided (2026-11-18):* current state only. Run graphs keep what
   each run saw; effective dates wait until a source provides them.
5. Who is allowed to review/promote facts, and what evidence is required for each
   property?
6. Which employee data may be sent to an AI provider, under what controls, and which
   fields must never leave the controlled environment?
7. What is the intended production graph store and deployment environment?
8. What retention, correction, deletion and access-request obligations apply?
9. Which Confluence spaces, Jira projects and Power BI workspaces are in scope, and who
   owns access approval?
10. Which business questions must the first trusted query interface answer?
11. How should values be normalised per property (case, whitespace, controlled
    vocabularies such as employment status)? *Decided (2026-11-18):* trim surrounding
    whitespace, lowercase `work_email`, compare exactly (ADR-0008). Controlled
    vocabularies wait for the allowed values.
12. What is the format of an employee ID, and how should a numeric Excel cell such as
    `1001.0` be read? *Decided (2026-11-18):* a whole-number cell is read as its digits (xlsx
    stores `1001.0` as `1001`); decimals, dates and booleans are quarantined. Leading
    zeros in numeric cells are lost, so ID columns should be text. The ID format itself
    is still unknown.
13. Who issues the employee IDs in each source? *Decided (2026-11-18):* an issuer is configured
    per source (the HR system for HR-keyed sources) and IDs from different issuers are
    never merged automatically.
14. What is the permanent ontology namespace? *Decided (2026-11-18):* a company-owned domain,
    not yet named. *Provisional default until then:*
    `https://example.org/employee-knowledge/ontology#`. Change it before any real data
    is stored.
15. Should the manager be modelled as a relationship between employees or as a
    manager-ID value? *Decided (2026-11-18):* a manager-ID string, as the source states it.
    Task-010 resolves it to an employee and reports broken references.
16. Which CI platform should run tests and lint? *Decided (2026-11-18):* GitHub Actions.

Provisional defaults are not business rules. Each stays marked as provisional in code and
docs until the project owner answers the question. No source is authoritative for any
property until Task-012 delivers an approved policy, and only the current state is
modelled.

Until these are answered, keep connector access disabled, ingest only synthetic data,
and leave ambiguous assertions untrusted.
