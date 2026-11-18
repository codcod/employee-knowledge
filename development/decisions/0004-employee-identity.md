# ADR-0004: Employee identity

- **Status:** Accepted (2026-11-18). The project owner confirmed the HR system as issuer
  and the per-source issuer key (architecture §13, questions 1 and 13).
- **Supersedes:** ADR-003 (one-line entry)
- **Related:** ADR-0001, ADR-0003, ADR-0007

## Context

Identity must be conservative (architecture §4.3). The old URI,
`urn:employee-knowledge:employee:{id}`, did not say who issued the ID. If HR and Jira
both used `E-100` for different people, the two would merge silently.

## Decision

- The canonical employee URI is `urn:employee-knowledge:employee:{issuer}:{id}`, with
  `issuer` and `id` percent-encoded.
- `issuer` is set per source in the source configuration (ADR-0007). The issuer of the
  synthetic example is `example-hr`.
- The employee resource carries `ek:employeeId` (the raw ID) and `ek:issuer`.
- An employee ID is the trimmed text of the source cell; a whole-number cell is read as
  its digits. Rows are quarantined, with a reason, when the ID is empty, a decimal, a
  date or a boolean (architecture §13 question 12).
- When one sheet has the same ID on more than one row, every one of those rows is
  quarantined as `duplicate employee ID`. Nothing is picked.
- Names, emails, departments and titles are never identity keys.
- IDs from different issuers are **never merged automatically**. Cross-issuer links will
  be reviewed decisions with evidence in a later ADR. Until then, employees from
  different issuers are distinct resources.
- `ek:managerEmployeeId` stays a string assertion, read as an ID from the same issuer as
  the record (architecture §13 question 15). Task-010 resolves it to an employee and
  reports broken references; the link is derived, not asserted.

## Alternatives considered

- **Raw ID with no issuer.** Silent cross-source collisions. Rejected.
- **Hashing the ID into the URI.** Hides nothing, because the ID is stored on the
  resource anyway, and makes URIs harder to debug. Rejected.
- **A global internal ID assigned by this system.** Needs an identity registry and match
  decisions before any data loads. Too early; revisit with cross-issuer matching.

## Consequences

- One employee seen by two systems with different ID schemes appears as two employees
  until a reviewed link exists. Their conflicts will not show up until then. This is
  deliberate.
- If the organisation confirms one issuer for all sources, every source sets the same
  `issuer` and nothing else changes.

## Migration

Employee URIs change, which changes every assertion ID (ADR-0003). Only synthetic local
stores exist, so delete them and re-ingest. If the issuer value changes later, that also
needs a rebuild.
