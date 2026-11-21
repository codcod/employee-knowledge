---
id: EK-003
title: Add data-quality and freshness findings
project: employee-knowledge
depends-on: [EK-004]
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EK-003 — Add data-quality and freshness findings

## Outcome

After this ships, the report lists six kinds of data-quality finding: invalid values,
unresolved identities, broken manager references, missing required properties, stale
values and values whose freshness is unknown. Each finding has a category, a rationale and
evidence references, and none of them touches trust state. The missing-required and
freshness findings appear only for properties that the authority policy (EK-004) marks
required or gives a freshness window.

## Description

Roadmap task: Task-010 in `development/roadmap.md`. Milestone M1.

Add missing-required-field, invalid-value, unresolved-identity, broken-manager-reference
and stale-data findings. Keep quality dimensions separate from trust status (architecture
§3.4). Per ADR-0004, `ek:managerEmployeeId` stays a string; this ticket resolves it to an
employee of the same issuer and reports references that do not resolve.

Refined 2026-11-21 (owner decisions):
- **Mechanism now, rules later.** Which properties are required and how fresh they must
  be are business rules (§13 Q2 and Q5, recorded by EK-014). This ticket reads them from
  the EK-004 policy, which ships with no real rows. Without a policy in force, only the
  three rule-free categories appear.
- **Hard dependency on EK-004** (owner sign-off 2026-11-21): `required` and
  `freshness_days` are fields of the EK-004 policy row.
- **Staleness uses `ek:observedAt` only.** Ingestion time is never treated as observation
  time (§13 Q4). When a freshness window applies but the source supplies no time, the
  finding is `freshness-unknown`. Excel sources never supply one, so every Excel
  assertion of a property with a window gets that finding.
- **Missing is per employee, across all sources.** A required property is missing when
  no source's latest run observed any assertion for it on that employee, whatever the
  trust state.

Soft couplings: EK-005 (query results could later carry these findings; not in scope),
EK-014 (Q1 rehire answer may add identity categories; Q2/Q5 answers become policy rows).

Re-graded 2026-11-21: complexity medium-high → medium and cost M-L → M. The rules come
from EK-004, and the remaining work is one module and one report section.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge   # child path "." (in-tree layout)
git checkout main && git pull --ff-only
git checkout -b feat/EK-003-quality-findings
```

Do all work on this branch, with local WIP commits. Publish-gated: no push and no merge
request without the owner's explicit approval (AGENTS.md, rules §0). This is a root-path
child, so tidy the WIP commits into atomic ones before presenting, and keep that history
by default. Before pushing, run
`git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'`; it
must print nothing. Merging is the human's.

### Prerequisite gate (hard)

EK-004 must be in `6-done/` and merged to `main`, with a `merged to main` line in its
History and `src/ek/policy.py` present on `main`. If it is not, stop and ask the owner. Do
not build on an unmerged EK-004 branch. Start from a clean tree, and check that
`uv run pytest` is green first.

### Confirmed design decisions (do not deviate without asking)

1. **Findings are computed when the report is built and never stored.** They make no
   graph writes and no trust changes, like absence (ADR-0003). The logic is in
   `src/ek/quality.py`: `findings(store, policy, now) -> list[dict]`, independent of the
   CLI. `now` is a parameter, so tests control time. Whether the policy is in force is
   checked with `ek.policy.in_force(policy, now.date())`, because EK-004 takes a `date`.
2. **Every finding has `category`, `rationale` and `evidence`.** It also has
   `employee`, `employee_id` and `issuer` where known, and `property` where it applies.
   `evidence` is a list of `{"assertion"?, "source", "source_reference", "observed_at"?}`
   entries that point back at the observations or quarantined records. A finding carries
   no trust state (§3.4).
3. **There is a fixed rationale per category and no severity scale.** Ranking severity
   is a business judgement that waits for the data owner. The acceptance criterion
   "severity/rationale" is met by the rationale.
4. **The categories are closed:**
   - `invalid-value`: an assertion with a `Violation` observation in any completed run,
     the same set as today's `validation_violations`. Evidence: the violating
     observations.
   - `unresolved-identity`: each quarantined record in the latest completed run of each
     source (missing, malformed or duplicate employee ID). Evidence: the source and the
     source reference; the rationale includes the quarantine reason.
   - `broken-manager-reference`: an `ek:managerEmployeeId` assertion whose value is not
     the `ek:employeeId` of any `ek:Employee` with the same `ek:issuer` in the trusted or
     untrusted graph. Resolution never crosses issuers and never uses names (ADR-0004).
     It covers every assertion, whatever its trust or observation state.
   - `missing-required`: for each property the policy marks `required = true`, and each
     employee observed in at least one source's latest run, no assertion for that
     property on that employee was observed in any source's latest run. Evidence: the
     employee's observations in those latest runs.
   - `stale`: for each property with `freshness_days`, an assertion whose newest
     `ek:observedAt` is older than `now - freshness_days`. Evidence: that observation.
   - `freshness-unknown`: for the same properties, an assertion that has no
     `ek:observedAt` on any observation. Evidence: its observations. The rationale says
     ingestion time is not used.
5. **No policy, or a policy not yet in force, means only the first three categories
   run.** The report says the required and freshness checks are off because no authority
   policy is in force.
6. **The existing report keys stay** (`validation_violations`, `quarantined`), because
   `report-json` is a documented interface. A new `findings` key holds all six categories,
   sorted by `(category, issuer, employee_id, property, first evidence reference)`.
7. **In the Rich report, one "Data-quality findings" table replaces the "Invalid values"
   and "Quarantined rows" tables.** Its columns are Category, Employee, Property,
   Evidence (source references) and Rationale. It prints no values, so findings add no
   employee data to the screen beyond what the discrepancy table already shows.

### Tasks

#### Task 1 — `src/ek/quality.py`

- Implement `findings(store: KnowledgeStore, policy: Policy | None, now: datetime) ->
  list[dict]`, following decisions 1–5.
- Reuse what exists: `store.latest_runs()`, `store.observed()`, `store.observations()`,
  `store.quarantined()`, `store.assertions()`, and `ek.policy.in_force` from EK-004.
- If employee lookup by issuer needs a store read, add one read-only method to
  `KnowledgeStore` (`src/ek/graph/store.py`), for example `employee_ids() ->
  set[tuple[str, str]]` of (issuer, id). No writes.
- Rationale strings are module constants, one per category.

#### Task 2 — Report wiring

- `src/ek/reconcile.py`: `build_report(store, policy=None, today=None, now=None)` adds
  `"findings": quality.findings(store, policy, now or datetime.now(UTC))`.
- `src/ek/cli.py` `report`: the table from decision 7 replaces the two tables, with a
  note line when the policy checks are off. `report-json` needs no CLI change beyond
  passing the policy, which EK-004 already does.

#### Task 3 — Tests (`tests/test_quality.py`, plus `tests/test_report.py` updates)

All synthetic, built with `ReadResult` and `EmployeeRecord`. Set `observed_at` on records
where freshness is tested. Cover:
- **invalid-value:** a violating value gives a finding with its source reference; a
  conforming value gives none.
- **unresolved-identity:** the latest run's quarantined rows only (an older run's rows
  are not reported); duplicate-ID rows are included.
- **broken-manager-reference:**
  - A manager ID resolves through an employee known only from another source of the same
    issuer: no finding.
  - The same ID under a different issuer: finding.
  - A missing ID: finding.
  - An accepted manager assertion still gets its finding (quality is not trust).
- **missing-required:**
  - The property present in one source only: no finding.
  - The property seen only in an older run: finding.
  - A required property with no policy in force: no finding.
  - A future `effective_from`: no finding.
- **stale and freshness-unknown:**
  - `observed_at` exactly at the window boundary: not stale.
  - One second older: stale.
  - No `observed_at`: `freshness-unknown`.
  - A property with no window: neither finding.
- **Invariants (regression):** findings leave `len(store.dataset)` unchanged, change no
  `store.state(...)`, and leave `check_projection()` empty; every finding has a
  non-empty `category`, `rationale` and `evidence`.
- **CLI:** the `report` output has the "Data-quality findings" table and no "Invalid
  values" table; the `report-json` JSON has `findings`. Update existing report tests that
  assert the old table titles, and add `"findings"` to the top-level key-set assertion in
  `tests/test_report.py`. EK-004 has already added `"policy"` to it.

### Acceptance test

```
uv sync --extra dev
uv run pytest tests/test_quality.py -v      # all pass
uv run pytest                                # all pass
uv run ruff check . && uv run ruff format --check .

# Manual, synthetic only:
export EMPLOYEE_KNOWLEDGE_STORE="$(mktemp -d)/store.trig"
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export --config examples/sources.toml
uv run employee-knowledge ingest-excel examples/employees-directory.xlsx --source-id people-directory --config examples/sources.toml
uv run employee-knowledge report --config examples/sources.toml --policy /nonexistent.toml
#   broken-manager-reference for E-1002 (manager E-1004 is not an employee)
#   unresolved-identity for employees-directory.xlsx#Directory!5 (missing employee ID)
#   note: required/freshness checks off (no authority policy)
uv run employee-knowledge report --config examples/sources.toml --policy examples/policy.toml
#   additionally: freshness-unknown for each department assertion (Excel gives no time);
#   no missing-required (every employee has a department)
```

### Docs update (mandatory when user-facing)

- `docs/trust-model.md`: add a "Data-quality findings" section covering the six
  categories, the rationale, that findings are computed and never stored or used to
  change trust, and that ingestion time is not observation time. Update the Discrepancies
  bullet list, which now points at the findings table for invalid values and unusable
  rows.
- `docs/operating.md` "Report discrepancies": the new table, the `findings` JSON key, and
  how policy rows turn on the required and freshness checks.
- `development/architecture.md`: in §4.6, note that findings are computed per report and
  never stored; in §10, add `quality.py`; in §13 Q15, note that EK-003 delivers the
  manager-reference check.
- `development/roadmap.md`: a Task-010 progress line.
- The project keeps no changelog. `docs/` must not link to `development/`.

### Finish (mandatory)

1. Acceptance test green; `uv run pytest` and both ruff checks clean.
2. Docs updated.
3. Write the summary: files touched, decisions honoured, and anything deferred. Name the
   no-severity-scale choice (decision 3) for the owner to confirm.
4. Suggested commit message:

   ```
   feat(report): add data-quality and freshness findings (EK-003)

   Invalid values, unresolved identities, broken manager references, and,
   where the authority policy sets them, missing required properties, stale
   and freshness-unknown values. Computed per report with evidence
   references; never stored and never change trust.
   ```

5. Tidy up before presenting: this is a root-path child (`path = "."`), so rebase the WIP
   commits into a few atomic commits.
6. Commit locally on the branch; do not push or open an MR. Move the ticket to
   `4-in-review/` (`pickle ticket move EK-003 in-review --reason "acceptance green"`).

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-010 when Brine was set up
- 2026-11-19 — description patched (EK-001 review, step 8): the §13 answers are recorded by EK-014, split from EK-001
- 2026-11-21 — refined. Owner decisions: mechanism now, rules from the EK-004 policy (new hard depends-on EK-004, owner sign-off); staleness from ek:observedAt only, otherwise freshness-unknown; missing-required per employee across all sources' latest runs. Re-graded complexity medium-high → medium, cost M-L → M. Plan written
- 2026-11-21 — TO DO → READY: plan complete
- 2026-11-21 — folded EK-004 applicability-gate G9: call `in_force(policy, now.date())`; the report key-set test gains `findings`
