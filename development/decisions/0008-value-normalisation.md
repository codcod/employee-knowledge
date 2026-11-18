# ADR-0008: Value normalisation

- **Status:** Accepted (2026-11-18)
- **Related:** ADR-0003, ADR-0006

## Context

ADR-0003 builds the assertion ID from the normalised value, so the normalisation rule
decides which source values count as the same claim. The provisional rule was "trim
surrounding whitespace only" (architecture §13, question 11). With it, `Taylor@Example.com`
and `taylor@example.com` were reported as a discrepancy, although they are the same
mailbox in practice.

## Decision

- Every value: trim surrounding whitespace. A value that is blank after trimming is not
  an assertion.
- `work_email`: also lowercase.
- Every other property is compared exactly, case included.
- `ek:rawValue` on each observation keeps the exact source text.
- The rule lives in `ek.ingest.normalise`.

## Alternatives considered

- **Trim only.** Reports case-only email differences as conflicts. Rejected.
- **Controlled vocabularies** (employment status, department). Needs the allowed values
  from the data owner. Deferred, not rejected.
- **Case-fold every property.** Hides real differences in names and titles. Rejected.

## Consequences

- Assertions from different sources that differ only in email case are now one value in
  the report.
- Strictly, the local part of an email address can be case-sensitive. No mainstream mail
  system treats it so; accepted.

## Migration

Assertion IDs change for every email value that had upper-case letters. Only synthetic
local stores exist, so delete them and re-ingest. A future change to the rule needs a new
ADR and the same rebuild.
