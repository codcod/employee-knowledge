# ADR-0010: Source-authority policy

- **Status:** Proposed (2026-11-21). It becomes Accepted when the project owner approves
  EK-004 at review.
- **Related:** ADR-0002, ADR-0007, ADR-0009

## Context

Source authority is per property (architecture §6). Until a policy is approved, every
conflict stays unresolved and every fact needs a review. The project owner decided this
on 2026-11-18 (§13 Q3). Review events have recorded `ek:policyVersion "none"` since
ADR-0002, because no policy existed. EK-003 also needs two per-property business rules:
which properties are required, and how fresh a value must be.

Which source is authoritative for which property is the data owner's decision, and it is
still open (§13 Q3 and Q5). The mechanism can be built now. The rules cannot be written
yet.

## Decision

**One versioned TOML policy file, read with `tomllib`.** It lives at
`config/policy.toml`, a local, git-ignored file. `--policy` points elsewhere.
`examples/policy.toml` is a synthetic example, and its rows are not decisions. This
follows ADR-0007: the project is generic (ADR-0009), so a real organisation's policy
never lives in this repository.

**Schema.**

| Key | Required | Meaning |
|---|---|---|
| `version` | yes | Non-blank string, recorded on review events. |
| `effective_from` | yes | A TOML date (not a date-time). The policy is in force from this day (UTC). |
| `[[properties]]` | no | One row per property. |
| `property` | yes | A configuration field name (`department`, …). Each property at most once. |
| `authoritative` | yes | Source ids, possibly empty. |
| `secondary` | no | Source ids that are acceptable but not authoritative. Disjoint from `authoritative`. |
| `freshness_days` | no | A positive integer. Read by data-quality checks (EK-003). |
| `required` | no, default `false` | Whether every employee must have the property. Read by EK-003. |
| `reviewer_roles` | no | Roles permitted to review the property, recorded for people to read. |
| `conflict_rule` | yes | `manual` or `prefer-authoritative`. `prefer-authoritative` needs at least one authoritative source. |

Unknown keys are an error at both levels, as in ADR-0007. Every source id must be a
configured source, so a typo cannot quietly leave a property without authority.

**`required` is added to the §6 policy row.** That keeps every per-property business rule
in one reviewed, versioned file.

**A policy never waives review.** Architecture §6 lists "whether human review is always
required" as a field of a policy row. AGENTS.md ("No autonomous promotion") and §3.3
already settle that question: review is always required. The schema therefore has no
such key, and a file that tries to add one is refused as an unknown key. The alternative
would be a key that could only ever hold one value, or one that allows automatic
promotion, which the invariants forbid.

**Putting the file in place is the approval.** The model has no "approved" flag. A
deployment owner approves a policy by putting it at the configured path, through the
same review process that governs `sources.toml`. A policy whose `effective_from` is in
the future is not in force, and it is treated as no policy.

**Evaluation recommends and never decides.** For each discrepancy, the report shows one
of four outcomes:

- `no-policy`: no policy is in force, or the policy has no row for the property.
- `manual`: the row leaves the choice to a reviewer.
- `recommend`: under `prefer-authoritative`, exactly one distinct value comes from
  authoritative sources. Its assertions are named.
- `unresolved`: under `prefer-authoritative`, no value, or more than one, comes from
  authoritative sources.

Only facts in state candidate, needs-evidence or accepted count. A person has already
set rejected and superseded facts aside, and `accept` refuses a rejected one. A value
that the latest run no longer contains still counts, and the rationale says so.
Rationales name sources, never values. Evaluation writes nothing, and trust changes only
through review events (ADR-0002).

**Review events record the policy in force.** `ek:policyVersion` holds the version of
the policy in force when the event was recorded, even if the policy has no row for the
property, because it shows which policy governed the decision. It holds `"none"` when no
policy file exists or the policy is not yet in force.

**Roles are recorded, not checked.** Reviewers are local labels (architecture §4.7).
Checking a typed-in role would look like access control, and it is not. Enforcement
waits for real identity.

**Failure handling.** A missing file at the default path means no policy, and the CLI
says so. A missing file named with `--policy`, or a file that is unreadable or invalid,
makes `report`, `report-json` and every `review` command exit with status 1. No event is
written, and nothing falls back to `"none"`.

## Alternatives considered

- **Authority keys in `sources.toml`.** ADR-0007 forbids authority there, so that trust
  cannot be configured per source by accident. Rejected.
- **The policy stored as RDF in the graph store.** It would make the policy queryable.
  But the version string on each event already makes decisions traceable, and a second
  copy of the policy in the store could drift from the reviewed file. Rejected for now.
- **SHACL shapes for authority and required properties.** These are business rules
  about which value to believe, not structure (ADR-0006). Rejected.
- **A policy key that turns review off for a property.** It contradicts the
  no-autonomous-promotion invariant. Rejected.

## Consequences

- No source becomes authoritative until a deployment adds a policy that names it. The
  example policy is never read unless someone copies it into place.
- The audit trail shows which policy governed each decision.
- A recommendation is a hint for the reviewer. Accepting it is still a review event with
  a reason.
- A policy change without a `version` bump goes unnoticed. Review catches it; the loader
  cannot.

## Migration

None. Existing events keep `"none"`, which was true when they were recorded.
