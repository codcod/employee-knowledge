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
  be are business rules (related to §13 Q2; no §13 question asks about freshness yet, and
  EK-014 adds one). This ticket reads them from
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
     ingestion time is not used. An `ek:observedAt` without a timezone is not used
     either (owner decision 2026-11-24): if any observation has a time without a
     timezone, or one that cannot be read, the finding is `freshness-unknown` with a
     rationale saying so, never `stale` (review F2). UTC is never assumed.
5. **No policy, or a policy not yet in force, means only the first three categories
   run.** The report says the required and freshness checks are off because no authority
   policy is in force.
6. **The existing report keys stay** (`validation_violations`, `quarantined`), because
   `report-json` is a documented interface. A new `findings` key holds all six categories,
   sorted by `(category, issuer, employee_id, property, first evidence reference)`.
7. **In the Rich report, one "Data-quality findings" table replaces the "Invalid values"
   and "Quarantined rows" tables.** Its columns are Category, Employee, Property,
   Evidence (source references) and Rationale. It prints no values, so findings add no
   employee data to the screen beyond what the discrepancy table already shows. Its
   cells are `escape()`d: references and reasons are source text, not Rich markup
   (the rest of the CLI is EK-015's).

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
  `"findings": quality.findings(store, policy, now)`, where `now` defaults to
  `datetime.now(UTC)` and `today` defaults to `now.date()`, so the two agree.
- `src/ek/cli.py` `report`: the table from decision 7 replaces the two tables, with a
  note line when the policy checks are off (not repeating `_policy`'s own "No authority
  policy loaded" line). Update the `report` docstring. `report-json` needs no CLI change beyond
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
  - `observed_at` without a timezone: `freshness-unknown`, not stale.
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
uv run employee-knowledge report --config examples/sources.toml   # no config/policy.toml: no policy
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

### Review — round 1 (2026-11-24)

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | blocking | correctness | — | `build_report(today=…)` without `now` checks the policy for the header and discrepancies on `today`, but for findings on `now.date()`, so the two can disagree | repro: `build_report(store, policy(effective=2026-01-01, required=True), today=date(2025,12,31))` → `policy.in_force` False, yet findings hold `missing-required` (`src/ek/reconcile.py:22`) | use one date: `today` given and `now` not → findings use `today` too (e.g. pass `today` into `quality.findings`) |
| F2 | blocking | correctness | — | A newer `ek:observedAt` without a timezone is ignored, so an older zoned time makes the value `stale` although it was observed yesterday | repro: run 1 `2020-01-01T00:00:00+00:00`, run 2 `2026-05-31T00:00:00`, window 30, now 2026-06-01 → `['stale']` (`src/ek/quality.py` freshness branch); EK-003 decision 4 (owner, 2026-11-24): UTC never assumed | any `ek:observedAt` present but unusable → `freshness-unknown` (UNKNOWN_TZ), never `stale` |
| F3 | blocking | correctness | — | A naive `now` makes `build_report`/`findings` raise `TypeError` as soon as a property has a freshness window | repro: `findings(store, policy(freshness=30), datetime(2026,6,1))` → `TypeError: can't compare offset-naive and offset-aware datetimes` | reject a naive `now` with a clear `ValueError` at the `findings` boundary |
| F4 | blocking | correctness | — | The findings table drops the source: the replaced "Quarantined rows" table had a Source column, so rows from two sources with the same workbook name cannot be told apart | `src/ek/cli.py` findings table prints only `source_reference`; old code printed `_short(q["source"])` | show the short source id with each evidence reference |
| F5 | non-blocking | design | noted | An assertion with no observation in a completed run gives empty evidence, and the sort on `evidence[0]` raises `IndexError` | repro on a hand-built store only; ingest writes the run and its assertions together (delegated reviewer ruled it unreachable) | none now |
| F6 | non-blocking | design | noted | The table no longer shows validation messages for invalid values | intentional: messages may hold values (`cli.py` IngestError comment; decision 7); `report-json` keeps them per observation | none |
| F7 | non-blocking | spec-unclear | noted | Stale, freshness-unknown and broken-manager findings also cover assertions no latest run still contains, so superseded values keep their findings | decision 4 ("every assertion, whatever its trust or observation state") | data owner to confirm when the §13 freshness question (EK-014) is answered |
| F8 | non-blocking | correctness | noted | A `freshness_days` large enough to overflow `timedelta`/`datetime` passes policy validation and crashes the report | repro (delegated): `freshness_days=1_000_000` with a zoned `observed_at` → `OverflowError`; no adapter supplies `observed_at` today | bound `freshness_days` in `policy._row` when a source first supplies observation times |
| F9 | non-blocking | test-gap | fixed inline | No test that the "checks are off" note is absent when a policy is in force | `tests/test_quality.py::test_cli_shows_findings_table_and_json_key` covers only no policy | add an in-force CLI assertion (in the rework commits) |
| F10 | non-blocking | stale-xref | fixed inline | The new §4.6 paragraph omits freshness-unknown from the categories | `development/architecture.md` §4.6 | add it (in the rework commits) |
| F11 | non-blocking | correctness | folded | The existing report tables print values, IDs and references without `escape` (pre-existing) | code-review tool, `cli.py` `row()` | EK-015 already owns it |
| F12 | non-blocking | correctness | folded | `escape()` leaves terminal control characters (ESC/OSC) in source text, so a workbook or sheet name can inject terminal sequences (pre-existing, whole CLI) | repro (delegated): `escape("wb\x1b]0;pwned\x07…")` printed with `force_terminal=True` keeps `\x1b]0;pwned` | EK-015: item added for C0/C1 control characters |
| F13 | non-blocking | correctness | folded | Emoji shortcodes survive `escape()` in the findings cells | repro (delegated): `escape('Team:fire:.xlsx#S!2')` renders 🔥 | EK-015 already covers emoji; findings table added to its regression list |

Dispositions: 4 blocking (F1–F4, → rework); non-blocking: 4 noted (F5–F8), 2 fixed inline (F9, F10), 3 folded into EK-015 (F11–F13), 0 new tickets.
cost: estimated M, actual M

Checklist:
- [x] Reviewer independence (step 0): delegated — the orchestrator wrote the branch; a fresh sub-agent ran steps 1–4a. No delegated finding discarded.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` 0 errors, 0 warnings on the branch.
- [x] Implementation audit (steps 1, 2): delegated reviewer re-ran `uv run pytest` (202 passed), both ruff checks and the manual synthetic acceptance; tasks 1–3 and decisions 1–7 met.
- [x] Correctness hunt (step 3): host tool path — `/code-review medium` on `main...feat/EK-003-quality-findings`, run by the orchestrator; 8 findings, 0 discarded (4 important reproduced by orchestrator script; 1 pre-existing). Angle 7 ran separately (delegated reviewer, no sub-agents): 2 findings, plus F8 incidentally.
- [x] Consistency audit (step 4): delegated; F10.
- [x] Documentation audit (step 4a): delegated; coverage complete, no `docs/` → `development/` links, no docs build configured.
- [ ] Docs-readability pass (step 4b): conscious skip — optional, not run this round.
- [x] Findings recorded (step 5).
- [x] Ticket moved to `5-rework/` (step 6a).

### Rework fix record — round 1 (commit cc797d3; after the rebase onto `main`, eea2501 — same code, review R5)

- F1: `quality.findings` takes `today` (default `now.date()`) for the in-force check, and `build_report` passes its own `today`, so the header, recommendations and findings use one date. Test `test_report_uses_one_date_for_policy_and_findings`.
- F2: any `ek:observedAt` present but unusable (no timezone, unreadable) gives `freshness-unknown` (UNKNOWN_TZ, evidence = those observations), never `stale`. Test `test_newer_time_without_timezone_is_never_stale_on_an_older_one`; `docs/trust-model.md` says so.
- F3: `findings` raises `ValueError("now must be timezone-aware")` for a naive `now`. Test `test_naive_now_is_refused`.
- F4: the Evidence cell shows `<source id>: <source reference>`. CLI test checks two sources with the same reference; `docs/operating.md` updated.
- F9 (fixed inline): the CLI test also runs `report` with an in-force policy and asserts the "checks are off" note is absent.
- F10 (fixed inline): §4.6 lists freshness-unknown.
- Checks: `uv run pytest` 205 passed; `ruff check` and `ruff format --check` clean; manual synthetic acceptance matches the plan.

### Review — round 2, scoped re-review (2026-11-24)

F1–F4 verified closed against the fix diff; each regression test fails on the round-1 code. F9 and F10 confirmed.

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| R1 | non-blocking | correctness | noted | Findings that tie on the decision-6 sort key (same category, employee, property and first reference, different sources) come out in an order that depends on `PYTHONHASHSEED` after a store reload | repro (delegated): five sources, same ref `wb.xlsx#S!2`, freshness 30, save/reload → seeds 1/2/3 give three orders | add the source (or assertion URI) as a last sort-key element; extends decision 6, so the owner decides |
| R2 | non-blocking | docs-gap | fixed inline | `docs/trust-model.md` freshness-unknown row and paragraph described less than the F2 fix ships (one unusable time is enough; unreadable times count too) | `docs/trust-model.md` category table vs paragraph | reworded (branch commit `docs: describe unusable observation times precisely (EK-003)`) |
| R3 | non-blocking | stale-xref | fixed inline | Decision 4's freshness-unknown prose described the pre-F2 rule | this ticket, decision 4 | amended (History line) |
| R4 | non-blocking | spec-unclear | noted | A later run with no time does not stop an older zoned time from giving `stale` (only unusable times do) | repro (delegated): run 1 `2020-01-01T00:00:00+00:00`, run 2 no time, window 30 → `stale` | data owner decides with F7 and EK-014's freshness question |
| R5 | non-blocking | stale-xref | fixed inline | The round-1 fix record named the pre-rebase SHA | `git branch --contains cc797d3` empty; `git diff cc797d3 eea2501` touches `tickets/` only | heading names both |

Dispositions: 0 blocking; 2 noted (R1, R4), 3 fixed inline (R2, R3, R5), 0 folded, 0 new tickets. Verdict: done.
cost: estimated M, actual M

Checklist:
- [x] Reviewer independence (step 0): delegated — fresh sub-agent; one candidate discarded by it (a tzinfo whose `utcoffset()` is None: no caller can build one). No delegated finding discarded by the orchestrator.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` 0/0.
- [x] Implementation audit (steps 1, 2): scoped to F1–F4, F9, F10 and the fix diff; `uv run pytest` 205 passed, ruff clean, manual synthetic acceptance matches.
- [x] Correctness hunt (step 3): one-pass angle hunt (all 8 angles, angle 7 included) by the delegated reviewer, no sub-agents; R1 and R4 reproduced.
- [x] Consistency audit (step 4): R2, R3, R5.
- [x] Documentation audit (step 4a): coverage complete; no `docs/` → `development/` links; no docs build.
- [ ] Docs-readability pass (step 4b): conscious skip — optional.
- [x] Findings recorded (step 5).
- [x] Ticket moved to `6-done/` (step 6b).
- [x] Other references (step 7): roadmap Task-010 progress line and architecture §4.6/§10/§13 Q15 updated on the branch; EK-015 and EK-014 carry their folded items.
- [x] Impact sweep (step 8): no ticket lists EK-003 in `depends-on:`. EK-005 (soft coupling) can later carry findings in query results; its plan does not assume anything EK-003 changed. EK-014 already carries the freshness question.

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-010 when Brine was set up
- 2026-11-19 — description patched (EK-001 review, step 8): the §13 answers are recorded by EK-014, split from EK-001
- 2026-11-21 — refined. Owner decisions: mechanism now, rules from the EK-004 policy (new hard depends-on EK-004, owner sign-off); staleness from ek:observedAt only, otherwise freshness-unknown; missing-required per employee across all sources' latest runs. Re-graded complexity medium-high → medium, cost M-L → M. Plan written
- 2026-11-21 — TO DO → READY: plan complete
- 2026-11-21 — folded EK-004 applicability-gate G9: call `in_force(policy, now.date())`; the report key-set test gains `findings`
- 2026-11-24 — applicability gate (fresh sub-agent): 0 blocking, 5 non-blocking, routing approved by the owner
- 2026-11-24 — plan amended inline: acceptance step drops `--policy /nonexistent.toml` (EK-004 makes a missing named file exit 1); an `ek:observedAt` without a timezone gives `freshness-unknown` (owner decision); §13 references corrected (Q2 related, Q5 dropped; freshness question folded into EK-014); `today` defaults to `now.date()`; findings-table cells escaped; `report` docstring updated
- 2026-11-24 — READY → IN DEVELOPMENT: picked up
- 2026-11-24 — IN DEVELOPMENT → IN REVIEW: acceptance green (202 tests, ruff clean; manual synthetic run matches plan)
- 2026-11-24 — IN REVIEW → REWORK: review round 1: 4 blocking (F1–F4)
- 2026-11-24 — REWORK → IN REVIEW: findings fixed (round 1)
- 2026-11-24 — plan amended inline: decision 4's freshness-unknown text now matches review F2 (any unusable time gives freshness-unknown) (review R3)
- 2026-11-24 — IN REVIEW → DONE: review round 2 clean: 0 blocking; round 1 F1–F4 fixed; dispositions 6 noted, 5 fixed inline, 3 folded (EK-015), 0 new tickets
