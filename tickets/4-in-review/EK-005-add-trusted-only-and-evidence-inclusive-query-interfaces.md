---
id: EK-005
title: Add trusted-only and evidence-inclusive query interfaces
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EK-005 — Add trusted-only and evidence-inclusive query interfaces

## Outcome

After this ships, a caller can look up facts about an employee, a property or both,
through the Python API or `employee-knowledge query`. The caller must name the trust
scope: `trusted` gives accepted assertions only, and `all` gives every assertion labelled
with its review state. Every result carries its provenance and flags conflicting values.
A trusted answer says how many untrusted candidate values exist, but never shows them.

## Description

Roadmap task: Task-013 in `development/roadmap.md`. Milestone M1.

Provide safe, read-only query methods for trusted answers and for diagnostic views that
include untrusted assertions (architecture §4.8). Include provenance in results.

Refined 2026-11-21 (owner decision):
- **A generic fact lookup first.** The business questions (§13 Q10) are not answered
  yet, since EK-014 records them. This ticket ships a lookup filtered by employee and/or
  property, with a mandatory trust scope. Named business-question templates are added
  once Q10 is answered, through a new ticket at that time.

Out of scope: SPARQL (EK-006 owns constrained SPARQL); applying a conflict-resolution
policy to the trusted view (EK-004 only recommends); attaching data-quality findings to
results (EK-003).

Soft couplings: EK-004 (policy recommendations could be shown later), EK-003 (stale
evidence could be disclosed later), EK-006 (builds on the scope and disclosure rules set
here), EK-014 (Q10).

Grades unchanged at refinement (high / medium / M).

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge   # child path "." (in-tree layout)
git checkout main && git pull --ff-only
git checkout -b feat/EK-005-trust-scoped-query
```

Do all work on this branch, with local WIP commits. Publish-gated: no push and no merge
request without the owner's explicit approval (AGENTS.md, rules §0). This is a root-path
child, so tidy the WIP commits into atomic ones before presenting, and keep that history
by default. Before pushing, run
`git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'`; it
must print nothing. Merging is the human's.

### Prerequisite gate (hard)

None: `depends-on: []`. Start from a clean tree on an up-to-date `main`, and check that
`uv run pytest` is green first. EK-003 and EK-004 are already merged into `main`, so
branching from `main` is enough; their report changes do not affect this module.

### Confirmed design decisions (do not deviate without asking)

1. **The trust scope is mandatory and has no default.** The Python API is
   `query_facts(store, *, scope: Scope, employee_id: str | None = None, issuer: str |
   None = None, property: str | None = None) -> list[dict]`, where `Scope` is a `StrEnum`
   with values `trusted` and `all`. `scope` is keyword-only and has no default. On the
   CLI, `--scope` is a required option, so leaving it out is a usage error (exit 2).
2. **Trusted scope reads facts from `urn:employee-knowledge:graph:trusted` only.** As
   defence in depth, it first runs `store.check_projection()`, which compares every
   assertion's graph with its derived state. On any mismatch it raises
   `QueryError("projection out of date; run rebuild-projection")` and returns nothing. A
   broken projection must never leak untrusted values.
3. **Untrusted candidates are counted and never shown in trusted scope.** For each
   (employee, property) group, a trusted result includes `untrusted_candidates: int`:
   the number of distinct values among assertions that are not accepted, for the same
   employee and property, whose value differs from every accepted value. The value
   strings and URIs of those assertions never appear. A group with no accepted assertion
   but with candidates is still returned, with empty `facts`, so a missing trusted value
   is disclosed (§4.8).
4. **Results are grouped by (employee, property).** Each group is `{"employee",
   "employee_id", "issuer", "property", "values", "conflict", "facts"}`, plus
   `untrusted_candidates` in trusted scope.
   - In trusted scope, `conflict` means more than one distinct accepted value (an
     accepted conflict, ADR-0002).
   - In `all` scope, it means more than one distinct value.
   - No value is ever picked.
5. **A fact carries its provenance:** `assertion`, `value`, `source`, `status` (the
   review state), `observed_in_latest_run` and `observations` (run, source reference,
   raw value, `observed_at`, validation). It also carries `latest_review`, or `None`:
   reviewer label, action, reason, policy version and time, from the latest audit event.
   The fact dict is built by the code that already builds it in
   `ek.reconcile.build_report`: extract that into one shared function rather than copy
   it.
6. **Filters.** `property` is a field name from `FIELD_PREDICATES`; an unknown name
   raises `QueryError`. `employee_id` without `issuer` matches that ID under every
   issuer. Results always name the issuer and are never merged across issuers
   (ADR-0004). No filter returns every group.
7. **Strictly read-only.** `src/ek/query.py` never calls `add_run`, `add_event`,
   `project`, `rebuild_projection` or `save`. Any new store methods are reads.
8. **Python over the store interface; no SPARQL.** EK-006 owns SPARQL.
9. **CLI.** `employee-knowledge query --scope trusted|all [--employee-id ID] [--issuer
   I] [--property P] [--json]`:
   - It prints a Rich table: Employee, Issuer, Property, Value, Source, State,
     References. Cells holding source text are `rich.text.Text`, so markup and emoji
     in the source are never interpreted (the EK-015 issue).
   - In trusted scope it adds a line per group with `untrusted_candidates > 0`: "N
     unaccepted value(s) not shown; use --scope all". "Unaccepted" means any state
     other than Accepted: Candidate, NeedsEvidence, Rejected or Superseded.
   - The table title states the scope and the graphs read.
   - `--json` prints the result list as JSON to stdout.
   - A `QueryError` exits 1.

### Tasks

#### Task 1 — Shared fact builder

In `src/ek/reconcile.py`, extract the per-assertion `fact` dict construction into
`fact(store, graph_id, assertion, graph, observations, latest_seen) -> dict`, or the
nearest equivalent. `build_report` keeps its output byte-identical, and the existing
`tests/test_report.py` must pass unchanged.

#### Task 2 — `src/ek/query.py`

- Define `Scope`, `QueryError(ValueError)` and `query_facts(...)`, following decisions
  1–8.
- Read assertions through the existing `store.assertions()`, which yields the graph
  each one is in, and keep only the trusted graph's for trusted scope. Run the leak
  guard through the existing `store.check_projection()`. No new graph-access method is
  needed, and graph access stays in `src/ek/graph/store.py`.
- Add `latest_review` through a read-only store helper over `store.events(assertion)` and
  `store.event(e)`.

#### Task 3 — CLI

Add `src/ek/cli.py` `query`, per decision 9. It opens the store, calls `query_facts`, and
prints or dumps the result. It never saves.

#### Task 4 — Tests (`tests/test_query.py`)

All synthetic. Cover:
- **Scope is mandatory:** `query_facts(store)` without `scope` raises `TypeError`; the
  CLI without `--scope` exits 2; an invalid scope value is refused.
- **No leak (regression):**
  - Ingest two sources that conflict on one property and accept one value.
  - The trusted JSON contains the accepted value, with `untrusted_candidates == 1`.
  - The serialised trusted output contains neither the other value's string nor its
    assertion URI.
  - Repeat the check with a rejected and a superseded assertion.
- **Leak guard:** corrupt the projection by adding an unaccepted assertion's triples to
  the trusted graph directly in the test. Trusted scope must raise `QueryError`, and
  `all` scope still works.
- **All scope:** both values, each with its state, and `conflict` is true.
- **Escaping:** the CLI table prints a bracketed synthetic value such as `[/x]`
  literally, without a `MarkupError`.
- **Accepted conflict:** two accepted different values give trusted `conflict` true and
  both shown.
- **Missing trusted value:** a candidate-only group in trusted scope has `facts == []`
  and `untrusted_candidates == 1`.
- **Provenance:** each fact has `source`, observations with `source_reference` and
  `run`, and `latest_review` with reviewer, reason and policy version after an accept.
- **Filters:** by employee only; by property only; an unknown property gives
  `QueryError`. The same ID under two issuers gives two groups, never merged.
- **Read-only:** the store file's bytes and `len(store.dataset)` are unchanged after the
  CLI `query` in both scopes.
- **Unchanged report:** `build_report` output is unchanged for the same fixture. This is
  covered by the existing `tests/test_report.py` passing unmodified.

### Acceptance test

```
uv sync --extra dev
uv run pytest tests/test_query.py -v        # all pass
uv run pytest                                # all pass; tests/test_report.py unmodified
uv run ruff check . && uv run ruff format --check .

# Manual, synthetic only:
export EMPLOYEE_KNOWLEDGE_STORE="$(mktemp -d)/store.trig"
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export --config examples/sources.toml
uv run employee-knowledge ingest-excel examples/employees-directory.xlsx --source-id people-directory --config examples/sources.toml
uv run employee-knowledge query --employee-id E-1002 --property department
#   exit 2: missing --scope
uv run employee-knowledge query --scope trusted --employee-id E-1002 --property department
#   no trusted value; "2 unaccepted value(s) not shown"
uv run employee-knowledge report-json --output "$(mktemp -d)/r.json"
#   accept the hr-export E-1002 department assertion ("People"):
uv run employee-knowledge review accept <uri> --reviewer demo --reason "checked"
uv run employee-knowledge query --scope trusted --employee-id E-1002 --property department
#   People (hr-export, Accepted), "1 unaccepted value(s) not shown"; "Product" absent
uv run employee-knowledge query --scope all --employee-id E-1002 --property department --json
#   both values with states Accepted / Candidate, conflict true
```

### Docs update (mandatory when user-facing)

- `docs/operating.md`: a new "Query facts" section covering the two scopes, filters,
  `--json`, what the untrusted-candidate line means, and the `rebuild-projection` hint on
  the leak-guard error. Add the query to the example run.
- `docs/trust-model.md`: a short "Trusted and diagnostic queries" section, and a
  "Current limitations" bullet saying no named business questions exist yet.
- `development/architecture.md`: in §4.8, note that the prototype lookup exists, and
  that named templates wait for §13 Q10; in §10, add `query.py`.
- `development/roadmap.md`: a Task-013 progress line.
- The project keeps no changelog. `docs/` must not link to `development/`.

### Finish (mandatory)

1. Acceptance test green; `uv run pytest` and both ruff checks clean.
2. Docs updated.
3. Write the summary: files touched, decisions honoured, and anything deferred (named
   templates until Q10).
4. Suggested commit message:

   ```
   feat(query): add trust-scoped fact lookup (EK-005)

   query_facts and `employee-knowledge query` require an explicit scope:
   trusted (accepted assertions only; untrusted candidates counted, never
   shown) or all (every assertion with its review state). Results carry
   provenance and flag conflicts. Read-only.
   ```

5. Tidy up before presenting: this is a root-path child (`path = "."`), so rebase the WIP
   commits into a few atomic commits (for example, the refactor of the fact builder, then
   the query module with CLI and tests, then docs).
6. Commit locally on the branch; do not push or open an MR. Move the ticket to
   `4-in-review/` (`pickle ticket move EK-005 in-review --reason "acceptance green"`).

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-013 when Brine was set up
- 2026-11-19 — description patched (EK-001 review, step 8): the §13 answers are recorded by EK-014, split from EK-001
- 2026-11-21 — refined. Owner decisions: generic fact lookup with mandatory scope now; named business-question templates wait for §13 Q10 (EK-014). Grades unchanged. Plan written
- 2026-11-21 — TO DO → READY: plan complete
- 2026-11-25 — applicability gate (independent sub-agent): no blocking findings; 4 non-blocking, routing approved by the owner. (1) the query table prints source text unescaped (EK-015 class) → inline; (2) the "rebase onto EK-003/EK-004" step is stale, since both are merged → note-and-close; (3) `store.assertions()` and `store.check_projection()` already exist → inline, reuse them; (4) "untrusted candidate" could be read as the Candidate state only → inline, say "unaccepted"
- 2026-11-25 — plan amended inline: the prerequisite gate says EK-003/EK-004 are merged; decision 2's leak guard uses `store.check_projection()`; decision 9 uses `rich.text.Text` cells and the "N unaccepted value(s) not shown" wording; Task 2 reuses `store.assertions()` and adds no graph-access method; Task 4 adds an escaping test; the acceptance comments use the new wording
- 2026-11-25 — READY → IN DEVELOPMENT: picked up
- 2026-11-25 — IN DEVELOPMENT → IN REVIEW: acceptance green
