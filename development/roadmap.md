# Roadmap and task backlog

The plan for milestones and the task descriptions. Status lives on the Pickle board
(`tickets/BOARD.md`): each open task has one ticket, listed after its heading. Tasks
finished in M0 are marked done here and have no ticket. Task IDs (`Task-NNN`) and ticket
IDs (`EK-NNN`) are separate number series.

Milestone M0 is defined by [architecture.md §11](architecture.md#11-first-implementation-milestone).

## Milestones

| Milestone | Status | Scope | Tasks |
|---|---|---|---|
| M0: Excel vertical slice | Done | Architecture §11: configured Excel mapping, deterministic identity, provenance-bearing assertions with run metadata, untrusted/trusted/audit graphs, SHACL validation, a second conflicting synthetic source, discrepancy report, audited promotion, idempotent re-ingestion. Task-001 (EK-001) carries on after M0 | Task-003 to Task-009, Task-011 |
| M1: Data quality and identity | Planned | Ambiguous identity detection, freshness and completeness findings, trusted-only and evidence-inclusive queries | Task-010, Task-013 |
| M2: Enterprise connectors | Planned | Confluence allow-listed spaces/pages; Jira allow-listed projects and fields; Power BI approved workspace/dataset access; all read-only and source-version-aware | Task-015 to Task-018 |
| M3: Assisted reconciliation | Planned | AI-proposed mappings, evidence-linked extraction, attribute-level authority policies, human review queue. No autonomous trust promotion. | Task-012 |
| M4: Production | Planned | Managed graph store, access control, encryption, backup/restore, read-only query service, approved SPARQL templates, NL→SPARQL, monitoring, runbooks | Task-014, tasks to be defined |

Task order: start with Task-001 and Task-002. Then implement Task-003 to Task-007 as the
first vertical slice. Task-009 and Task-011 prove discrepancy handling and trust governance.
Finish Task-008 before any repeated scheduled ingestion. Defer AI and enterprise connectors
until the core assertion and provenance model is stable. Keep the first active task
narrow and respect the board's WIP limits.

## Tasks

### Foundation

**Task-001: Confirm architecture decisions and domain vocabulary**
- Ticket: EK-001 (review pack), EK-014 (record answers).
- Review the architecture with the employee-data owner.
- Confirm the employee identifier strategy, initial employee properties, source naming,
  timestamp semantics and initial authority assumptions.
- Record unresolved decisions; do not invent source authority.
- Acceptance: decisions are recorded, ontology terms have definitions, and open
  questions are explicit.
- Progress: review pack ready (EK-001); answers wait for the data-owner session (EK-014).

**Task-002: Establish Python package, quality gates and repository hygiene**
- Ticket: EK-002.
- Verify package layout, CLI entry point, pytest, Ruff and CI.
- Add safe `.gitignore` rules for secrets, data stores, exports and reports.
- Acceptance: clean install, tests and lint run in CI; no sensitive fixtures are tracked.
- Progress: Done: CI runs on GitHub Actions on Python 3.11 (EK-002).

**Task-003: Define employee ontology and SHACL validation**
- Status: done in M0.
- Define Employee and the initial properties listed in architecture §4.4.
- Add SHACL constraints and validation tests.
- Acceptance: valid synthetic records pass; missing/invalid required fields produce
  actionable validation results.

### Ingestion and provenance

**Task-004: Define canonical source-record and assertion contracts**
- Status: done in M0.
- Specify normalised record, source metadata, ingestion-run and assertion structures.
- Include stable source record references, timestamps and mapping version.
- Acceptance: contract is documented and covered by tests; adapters do not make trust
  decisions.

**Task-005: Implement configurable Excel source adapter**
- Status: done in M0.
- Support workbook, sheet selection, header mapping, blank handling and row-level
  provenance.
- Keep source files read-only.
- Acceptance: tests cover missing columns, empty IDs, blank cells, multiple sheets and
  malformed workbook input.

**Task-006: Implement deterministic employee identity for employee-ID sources**
- Status: done in M0.
- Create canonical employee URI from stable organisation employee ID.
- Reject/quarantine missing IDs; do not use names as keys.
- Acceptance: repeat records with the same employee ID resolve consistently; ambiguous
  records are not merged.

**Task-007: Implement provenance-bearing assertion writer and named graphs**
- Status: done in M0.
- Store each observed value as an assertion resource with employee, predicate, value,
  source, source record, timestamps and ingestion metadata.
- Separate untrusted, trusted and audit graphs.
- Acceptance: assertions from two sources coexist even when values differ;
  persistence/reload retains graph membership and provenance.

**Task-008: Make ingestion idempotent and version-aware**
- Status: done in M0.
- Define assertion identity and source snapshot/version semantics.
- Avoid uncontrolled duplicates on unchanged re-ingestion while preserving changed
  observations.
- Acceptance: repeat ingestion tests demonstrate deterministic behaviour; changed source
  data does not erase prior evidence.

### Reconciliation and governance

**Task-009: Implement discrepancy detection and evidence-rich reports**
- Status: done in M0.
- Compare assertions by canonical employee and ontology property.
- Report distinct values, sources, record references, timestamps, validation and trust
  state.
- Acceptance: conflicting synthetic sources are both shown; no source value is silently
  discarded.

**Task-010: Add data-quality and freshness findings**
- Ticket: EK-003.
- Add missing-required-field, invalid-value, unresolved-identity,
  broken-manager-reference and stale-data findings.
- Keep quality dimensions separate from trust status.
- Acceptance: each finding has a category, severity/rationale and evidence reference.

**Task-011: Implement explicit review and audited promotion**
- Status: done in M0.
- Add promote/reject/supersede review actions, with reviewer identity, reason, timestamp
  and policy version.
- Enforce untrusted-to-trusted transition rules.
- Acceptance: only an explicit authorised action changes trust state; audit event
  persists; original provenance and competing assertions remain.

**Task-012: Define attribute-level source-authority policy model**
- Ticket: EK-004.
- Create versioned policy configuration per property, including authoritative sources,
  freshness, reviewer role and conflict rules.
- Do not populate unapproved assumptions as facts.
- Acceptance: policy evaluation is testable and a conflict without a policy remains
  unresolved/untrusted.

### User and AI interfaces

**Task-013: Add trusted-only and evidence-inclusive query interfaces**
- Ticket: EK-005.
- Provide safe, read-only query methods for trusted answers and diagnostic views that
  include untrusted assertions.
- Include provenance in results.
- Acceptance: callers must explicitly choose trust scope; tests prove untrusted values
  do not leak into trusted-only results.

**Task-014: Add constrained natural-language-to-SPARQL design/prototype**
- Ticket: EK-006.
- Only after the ontology and query interface stabilise.
- Use schema grounding, read-only validation, timeouts, result limits and
  provenance-aware answers.
- Acceptance: generated queries cannot update data or access unapproved graphs;
  ambiguous/conflicting answers are disclosed.

### Enterprise source expansion

**Task-015: Implement Confluence read-only adapter**
- Ticket: EK-007.
- Define allow-listed spaces/pages, page versions and evidence references.
- Acceptance: connector is read-only, scoped and produces source-version-aware
  assertions.

**Task-016: Implement Jira read-only adapter**
- Ticket: EK-008.
- Define allowed projects, object types/fields and stable user/issue references.
- Acceptance: connector is read-only, scoped and preserves update/version metadata.

**Task-017: Implement Power BI read-only adapter**
- Ticket: EK-009.
- Define approved workspaces/datasets, refresh metadata and row/field provenance.
- Acceptance: connector is read-only and does not treat a report as authoritative
  without an explicit policy.

**Task-018: Add source onboarding and operational controls**
- Ticket: EK-010.
- Document connector credentials, scopes, scheduling, retries, rate limits, retention,
  source offboarding and audit.
- Acceptance: a new source can be onboarded through documented configuration and review
  without code changes where possible.
