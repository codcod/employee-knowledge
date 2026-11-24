---
id: EK-004
title: Define attribute-level source-authority policy model
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EK-004 — Define attribute-level source-authority policy model

## Outcome

After this ships, an operator can write a versioned policy file that names, for each
property, the authoritative and secondary sources, a freshness window, whether the property
is required, the permitted reviewer roles and a conflict rule. The report shows each
discrepancy's policy recommendation, or "no policy: unresolved". Review events record the
version of the policy in force instead of `none`. A policy never changes trust state.

## Description

Roadmap task: Task-012 in `development/roadmap.md`. Milestone M3.

Create versioned policy configuration per property: authoritative sources, freshness,
reviewer role and conflict rules (architecture §6). Do not populate unapproved assumptions
as facts. The project owner decided on 2026-11-18 that no source is authoritative until
this policy exists and is approved. A policy may recommend; it never changes trust state
without a review event (ADR-0002).

Refined 2026-11-21 (owner decisions):
- **Mechanism now, rules later.** This ticket ships the policy model, loader, evaluation
  and wiring with no real policy rows. The data owner's answers (EK-014, §13 Q3 and Q5)
  arrive later as rows in a deployment's own policy file. Tests and examples use
  synthetic rules only.
- **The policy also holds `required`.** Required properties and freshness windows both
  live in this policy, so EK-003 (data-quality findings) reads them from here and depends
  on this ticket. This extends the §6 policy row, so an ADR records it.
- **The file lives like `sources.toml`:** `config/policy.toml` (git-ignored), with
  `examples/policy.toml` as a synthetic example.
- **Reviewer roles are recorded, not checked.** Reviewers are local labels (architecture
  §4.7), so checking a typed-in role would look like access control. Enforcement waits
  for real identity.

Soft couplings: EK-003 (reads `required` and `freshness_days`; hard-depends on this
ticket), EK-005 (trusted queries surface accepted conflicts; resolution by policy is not
in scope there), EK-014 (Q3 and Q5 answers become policy rows).

Re-graded 2026-11-21: complexity high → medium and cost L → M. The open design questions
were settled at refinement, and what is left is one loader, one evaluator and wiring.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge   # child path "." (in-tree layout)
git checkout main && git pull --ff-only
git checkout -b feat/EK-004-authority-policy
```

Do all work on this branch, with local WIP commits. Publish-gated: no push and no merge
request without the owner's explicit approval (AGENTS.md, rules §0). This is a root-path
child, so tidy the WIP commits into atomic ones before presenting, and keep that history
by default. Before pushing, run
`git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'`; it
must print nothing. Merging is the human's.

### Prerequisite gate (hard)

None: `depends-on: []`. Start from a clean tree on an up-to-date `main`, and check that
`uv run pytest` is green before the first change.

### Confirmed design decisions (do not deviate without asking)

1. **The policy is TOML at `config/policy.toml`, git-ignored, and `--policy` overrides
   the path.** It is read with `tomllib`, so there is no new dependency. It follows the
   ADR-0007 pattern: the project is generic (ADR-0009), so a real organisation's policy
   never lives in this repo. `examples/policy.toml` is synthetic.
2. **No real policy rows ship.** `examples/policy.toml` uses only the synthetic sources
   `hr-export` and `people-directory`. Its header comment says the rows illustrate the
   format and are not decisions.
3. **Schema.** Top level: `version` (a non-blank string, required) and `effective_from`
   (a TOML date, required), plus an array `[[properties]]`. Each row has:
   - `property`: a field name from `FIELD_PREDICATES` (for example `department`). An
     unknown name is an error, and each property appears at most once.
   - `authoritative`: a list of source ids. It may be empty.
   - `secondary`: a list of source ids, default empty. It must not share an id with
     `authoritative`.
   - `freshness_days`: optional. A positive integer, and a boolean is refused.
   - `required`: a boolean, default `false`.
   - `reviewer_roles`: optional. A list of non-blank strings.
   - `conflict_rule`: required, either `"manual"` or `"prefer-authoritative"`.
     `"prefer-authoritative"` with an empty `authoritative` list is refused, because it
     could never recommend anything (gate G10).

   Unknown keys are an error at both levels, for the same reason as ADR-0007: trust
   settings cannot be added by accident. `effective_from` must be a plain TOML date.
   `tomllib` reads a date-time as a `datetime`, which is a subclass of `date`, so the
   loader refuses it explicitly (gate G5).
4. **A policy never waives human review.** Architecture §6 lists "whether human review
   is always required" as a policy field. AGENTS.md "No autonomous promotion" and §3.3
   already answer it: review is always required. The schema therefore has no such key,
   and a key like `review_required` is refused as unknown. The ADR names this conflict
   and how it was resolved, and the owner approves it at review.
5. **Policy source ids are checked against the source configuration.**
   `load_policy(path, source_ids)` refuses an id that is not a configured source. A typo
   must not silently leave a property with no authoritative source.
6. **`required` is an addition to the §6 policy row** (owner decision 2026-11-21). One
   file holds every per-property business rule, and EK-003 reads `required` and
   `freshness_days` from it.
7. **Evaluation recommends and never decides.** `evaluate(policy, discrepancy)` returns
   an outcome and a rationale:
   - `no-policy`: no policy is in force, or it has no row for the property;
   - `manual`: the row's rule is `manual`;
   - `recommend`: the rule is `prefer-authoritative` and exactly one distinct value comes
     from authoritative sources. The outcome names those assertions;
   - `unresolved`: the rule is `prefer-authoritative`, but no value, or more than one
     distinct value, comes from authoritative sources.

   Only facts in state Candidate, NeedsEvidence or Accepted count. Rejected and
   Superseded facts are excluded, because a person already set them aside and `accept`
   refuses a Rejected one (owner decision 2026-11-21, gate G4). Facts that the latest run
   no longer contains still count, and the rationale flags them. The report's dicts hold
   strings: `evaluate` looks up the row by `URIRef(d["property"])` and matches sources by
   `ek.identity.source_uri(id)` (gate G3). Evaluation writes nothing to the graph. Trust state changes only through `review`
   (ADR-0002).
8. **A policy is in force when `effective_from` is on or before today (UTC).** A policy
   that is not yet in force is treated as no policy, and the CLI warns.
9. **Review events record the version of the policy in force.** That holds even when the
   policy has no row for the property, because the record shows which policy governed the
   decision. The version is `"none"` when no policy file exists or the policy is not yet in
   force. The `POLICY_VERSION` constant in `src/ek/review.py` is removed, and `review()`
   gains a keyword-only `policy_version: str = "none"`. The CLI always passes the loaded
   value.
10. **Reviewer roles are recorded in the policy only.** The review command does not check
    them (owner decision 2026-11-21). The report shows the permitted roles beside each
    discrepancy whose property has a row.
11. **A missing policy file at the default path means no policy; an invalid one, or a
    missing one named explicitly with `--policy`, is an error.** When there is no file at
    the default `config/policy.toml`, report and review say "no authority policy loaded"
    and carry on. (Amended 2026-11-24, review F4: a mistyped `--policy` path must not be
    recorded silently as "none".) A file that
    is unreadable or invalid makes `report`, `report-json` and every `review` command exit
    1 with the error, and no review event is written. They never fall back to `none`.
12. **When a policy file exists, the CLI also loads `--config`** (default
    `config/sources.toml`) to check the policy's source ids. A missing sources file is then
    an error.
13. **The logic is in `src/ek/policy.py`, independent of the CLI.** The CLI only loads
    files and prints.
14. **Putting the file in place is the approval.** The model has no "approved" flag. The
    deployment owner approves a policy by putting it at the configured path, which
    follows the same review process as `sources.toml`. The ADR says this (gate G11).

### Tasks

#### Task 1 — ADR and architecture

- Write `development/decisions/NNNN-authority-policy.md`, using the next free ADR number,
  with status Accepted on owner approval at review. Cover context, the decision
  (decisions 1–14), alternatives and consequences:
  - Alternatives: authority keys in `sources.toml` (rejected: ADR-0007 forbids authority
    there); the policy stored as RDF in the store (rejected for now: the version string
    on each event is enough); SHACL (rejected: these are business rules, not structure).
  - Migration: none. Existing events keep `"none"`.
- Add the ADR to `development/decisions/README.md`.
- Architecture §6: add `required` to the policy-row list, add the note that review is
  never waived (decision 4), and link the ADR. In §5.3, point "configured authority by
  property" at the policy. In §10, add `policy.py` and `examples/policy.toml` to the
  tree. In §13 Q3 and Q5, note that the mechanism exists and the rows await the data
  owner (EK-014). Also update the statements that would go stale (gate G8):
  - §13 Q3 ("a versioned policy exists (Task-012)");
  - the closing paragraph of §13 ("until Task-012 delivers an approved policy");
  - the comment on `ek:policyVersion` in the ADR-0002 example (`# until a policy exists
    (Task-012)`), which becomes a pointer to the new ADR.

#### Task 2 — `src/ek/policy.py`

- `PolicyError(ValueError)`.
- Frozen dataclasses: `PropertyPolicy` (with fields per decision 3, and `predicate:
  URIRef`) and `Policy(version: str, effective_from: date, properties: dict[URIRef,
  PropertyPolicy])`.
- `DEFAULT_POLICY = Path("config/policy.toml")`.
- `load_policy(path: Path, source_ids: set[str]) -> Policy | None` returns `None` when
  the file is missing and enforces decisions 3–5.
- `in_force(policy: Policy | None, today: date) -> bool`.
- `version_in_force(policy, today) -> str` returns the policy's version, or `"none"`.
- `evaluate(policy: Policy | None, discrepancy: dict, today: date) -> dict` returns
  `{"outcome", "rationale", "recommended": [assertion URIs], "reviewer_roles": [...]}`.
  The version is reported once, at the top level of the report (gate G12). It takes one discrepancy dict as built by
  `ek.reconcile.build_report`.

#### Task 3 — Report

- `src/ek/reconcile.py`: `build_report(store, policy=None, today=None)`. `today`
  defaults to the current UTC date. It adds a top-level `"policy": {"version",
  "in_force"}`, or `None`, and adds `"policy": evaluate(...)` to every discrepancy. The
  existing keys are unchanged.
- `src/ek/cli.py`: `report` and `report-json` gain `--policy` (default `DEFAULT_POLICY`)
  and `--config` (decision 12). After the discrepancy table, outside it so it does not
  wrap at 80 columns (gate G2), the report prints one line per discrepancy:
  `<employee_id> <property>: policy <version>: <outcome>: <rationale>`, plus the roles
  when present. With no policy, the line reads "no authority policy: unresolved". An
  invalid file prints the error and exits 1.

#### Task 4 — Review records the policy version

- `src/ek/review.py`: remove `POLICY_VERSION` and add `policy_version` (decision 9).
- `src/ek/cli.py` `_review` and its commands gain `--policy` and `--config`. They load
  the policy before recording anything, so an invalid policy writes no event, and pass
  `version_in_force(...)`.
- `src/ek/ontology/employees.ttl`: change the `ek:policyVersion` `rdfs:comment` to
  "Version of the authority policy in force when the review was recorded; 'none' when
  there was none." This is a comment only, so `shapes.ttl` is unchanged.

#### Task 5 — Example and hygiene

- `examples/policy.toml`: version `"example-1"` with a past `effective_from`. The
  `department` row has `authoritative = ["hr-export"]`, `secondary =
  ["people-directory"]`, `conflict_rule = "prefer-authoritative"`, `freshness_days =
  365`, `required = true` and `reviewer_roles = ["example-hr-reviewer"]`. The
  `job_title` row has `authoritative = []` and `conflict_rule = "manual"`. The header
  comment carries the decision 2 disclaimer.
- `.gitignore`: add `config/policy.toml`.

#### Task 6 — Tests (`tests/test_policy.py`, plus `tests/test_review.py` and `tests/test_report.py` updates)

All synthetic. Cover:
- **Loader, valid input:** a valid file; a missing file gives `None`.
- **Loader, file-level errors:** invalid TOML; an unknown top-level key; an unknown row
  key, including `review_required` (decision 4).
- **Loader, row errors:** an unknown property; a duplicate property; an unknown source
  id; an id in both `authoritative` and `secondary`.
- **Loader, value errors:** `freshness_days` of 0, -1, `"30"` or `true`; an invalid
  `conflict_rule`; a blank `version`; a TOML date-time for `effective_from` (G5);
  `prefer-authoritative` with `authoritative = []` (G10).
- **In force:** a future `effective_from` is not in force, and `version_in_force` gives
  `"none"`.
- **Evaluation:** no policy, or no row, gives `no-policy`; a `manual` row gives `manual`;
  a single authoritative value gives `recommend` with that assertion; two authoritative
  sources that disagree give `unresolved`; no authoritative fact gives `unresolved`; a
  Rejected or Superseded authoritative fact is ignored (G4). At least one evaluation test
  runs on real `build_report` output rather than a hand-built dict (G3).
- **Invariants (regression):**
  - `build_report` with a policy leaves `len(store.dataset)` unchanged, changes no
    `store.state(...)`, and `check_projection()` stays empty.
  - A conflict without a policy stays `Candidate`, in the untrusted graph, and gets
    `no-policy`.
  - A `recommend` outcome leaves both assertions `Candidate`.
- **Review:** the event records the in-force version; it records `"none"` with no policy
  and with a future policy. CLI: `review accept` with an invalid `--policy` exits 1 and
  the audit graph has no new event.
- **CLI report:** `--policy examples/policy.toml --config examples/sources.toml` shows the
  policy row, and with no policy file the output reads "no authority policy".
- Update existing tests that assert `policyVersion == "none"` only where they now pass a
  policy. Do not weaken them.
- **Existing tests the plan would otherwise break:**
  - `tests/test_report.py:151`: the report's top-level key set gains `"policy"` (G1).
  - `tests/test_repository.py` `FORBIDDEN_PATHS` gains `^config/policy\.toml$` (G6).
  - New `tests/conftest.py` with an autouse fixture that runs
    `monkeypatch.chdir(tmp_path)`, so CLI tests never read a developer's local
    `config/policy.toml` (G7). Check that tests using relative `examples/` paths still
    resolve them from `ROOT`.

### Acceptance test

```
uv sync --extra dev
uv run pytest tests/test_policy.py -v       # all pass
uv run pytest                                # all pass, no skips added
uv run ruff check . && uv run ruff format --check .

# Manual, synthetic only:
export EMPLOYEE_KNOWLEDGE_STORE="$(mktemp -d)/store.trig"
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export --config examples/sources.toml
uv run employee-knowledge ingest-excel examples/employees-directory.xlsx --source-id people-directory --config examples/sources.toml
uv run employee-knowledge report --config examples/sources.toml --policy examples/policy.toml
#   E-1002 department (People vs Product): "policy example-1: recommend", naming the hr-export value
uv run employee-knowledge report --config examples/sources.toml --policy /nonexistent.toml
#   exit 1: the named policy file does not exist (review F4)
(cd "$(mktemp -d)" && uv run --project "$OLDPWD" employee-knowledge report)
#   no config/policy.toml in that directory: "no authority policy: unresolved"
R="$(mktemp -d)/r.json"
uv run employee-knowledge report-json --output "$R" --config examples/sources.toml --policy examples/policy.toml
#   then accept the hr-export E-1002 department assertion URI from "$R":
uv run employee-knowledge review accept <uri> --reviewer demo --reason "checked" --config examples/sources.toml --policy examples/policy.toml
grep -c 'policyVersion "example-1"' "$EMPLOYEE_KNOWLEDGE_STORE"   # 1
```

### Docs update (mandatory when user-facing)

- `docs/trust-model.md`:
  - Add an "Authority policy" section: what a row says; that the policy recommends and
    never decides; that review is always required; that roles are informational.
  - Update the policy-version sentence (line 63).
  - Add a "Current limitations" bullet: roles are not checked.
- `docs/operating.md`: setting up `config/policy.toml`, `--policy` on `report`,
  `report-json` and `review`, and the example run.
- `docs/source-onboarding.md`: a newly onboarded source has no authority until an
  approved policy lists it.
- `examples/README.md`: list `policy.toml`.
- `development/`: the ADR and architecture edits (Task 1); add a Task-012 progress line
  to `development/roadmap.md`.
- The project keeps no changelog. `docs/` must not link to `development/`.

### Finish (mandatory)

1. Acceptance test green; `uv run pytest` and both ruff checks clean.
2. Docs updated and the ADR registered in the index.
3. Write the summary: files touched, decisions honoured, and anything deferred. Name
   decision 4 (§6 "review always required" resolved by the invariant) as an architecture
   decision the owner must approve.
4. Suggested commit message:

   ```
   feat(policy): add versioned source-authority policy (EK-004)

   Per-property policy (authoritative/secondary sources, freshness, required,
   reviewer roles, conflict rule) loaded from config/policy.toml. The report
   shows each discrepancy's recommendation; review events record the policy
   version in force. A policy never changes trust state.
   ```

5. Tidy up before presenting: this is a root-path child (`path = "."`), so rebase the WIP
   commits into a few atomic, correctly typed commits (for example, docs/ADR, the policy
   module with its tests, and the wiring).
6. Commit locally on the branch; do not push or open an MR. Move the ticket to
   `4-in-review/` (`pickle ticket move EK-004 in-review --reason "acceptance green"`).

## Review

Review 2026-11-24, branch `feat/EK-004-authority-policy` (47194bc, fb9a0fc).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | blocking | correctness | — | Policy strings are printed through `rich.print` unescaped, so they are read as Rich markup. A version such as `v2 [/draft]` makes `review` record the event and then exit 1 with a `MarkupError`. That contradicts "a refused action records nothing" (`docs/operating.md`). `[/x]` in roles or a property name crashes `report`. `[draft]` disappears from the screen while the event records it. | Reproduced: `review request-evidence <uri> … --policy p.toml` with `version = "v2 [/draft]"` gives exit 1, and `grep -c 'policyVersion "v2 \[/draft\]"'` on the store prints 1. Code: `src/ek/cli.py` `_policy`, `_policy_line`, and the `_review` print after `store.save()`. | Escape every interpolated policy string (`rich.markup.escape`), including `exc` in `_policy`. Add a regression test with a bracketed version and role, including the no-event-on-failure path. |
| F2 | blocking | correctness | — | `property = ["department"]` (or an inline table) raises a raw `TypeError` from the dict lookup instead of a `PolicyError`. That breaks EK-004 decision 11: an invalid file must exit 1 with the error. | Reproduced: `load_policy` gives `TypeError: cannot use 'list' as a dict key`, and `report --policy p1.toml` prints a traceback. Code: `src/ek/policy.py` `_row`, `name not in FIELD_PREDICATES`. | Check `isinstance(name, str)` before the lookup, and add a test. |
| F3 | blocking | correctness | — | A policy file that is not valid UTF-8 raises an uncaught `UnicodeDecodeError`, which breaks EK-004 decision 11. | Reproduced: a file with bytes `\xff\xfe` passed to `report --policy` prints a traceback. Code: the `try` block in `src/ek/policy.py` `load_policy`. | Catch `UnicodeDecodeError` as "cannot be read", and add a test. |
| F4 | blocking | correctness | — | An explicit `--policy` path that does not exist (a typo) is treated silently as "no policy". Review then records `policyVersion "none"` although the reviewer meant to apply a policy. The plan mandates this (EK-004 decision 11), and the owner changed that decision on 2026-11-24. | `src/ek/cli.py` `_policy`, `path.exists()` for every path. Plan acceptance step: `--policy /nonexistent.toml`. | A missing file at the default path still means no policy. A missing file named explicitly with `--policy` exits 1 and records nothing. Amend decision 11 and the acceptance step. |
| F5 | non-blocking | correctness | noted | The CLI's "not in force" warning and `build_report` each compute today, so a run that crosses UTC midnight on `effective_from` could warn and still evaluate the policy as in force. | `src/ek/cli.py` `_policy` (`_today()`), `src/ek/reconcile.py` `build_report` (`datetime.now`). Traced; the window is a few milliseconds once a year. | Pass one `today` from the CLI if this ever matters. |
| F6 | non-blocking | test-gap | noted | Only `property` was found to crash on a non-scalar value. Arrays and tables in the other row keys already give a clean `PolicyError`, but no test proves that. | Hand check: `conflict_rule = {x = 1}` and `required = [1]` give `PolicyError`. | Add type-fuzz cases if the loader changes again. |
| F7 | non-blocking | design | noted | `ek:policyVersion` records the version string, not the file's content, so two policies with one version cannot be told apart. ADR-0010's Consequences already accept this. | `src/ek/review.py:94`; ADR-0010 Consequences. | Record the file's sha256 later if audit traceability needs it. |
| F8 | non-blocking | spec-unclear | fixed inline | The outcome table in `docs/trust-model.md` says the report "names" the recommended value. It names the source, because rationales never carry values. | `docs/trust-model.md`, Authority policy table; `src/ek/policy.py` `evaluate`. | Reworded to: the report names its source; `report-json` lists its assertions. |
| F9 | non-blocking | correctness | new ticket (EK-015) | Pre-existing on `main`, not caused by this branch: workbook values, source references and `ConfigError`/`SourceError` messages go through `rich.print` unescaped. | Reproduced on `main` (76745dc): a synthetic department value of `[/x]` makes `report` exit with a `MarkupError` traceback. | EK-015, "Escape source and config text in CLI output". |

Disposition summary: 4 blocking (F1–F4) → rework. Non-blocking: 1 fixed inline (F8), 1 new ticket (F9 → EK-015), 3 noted (F5, F6, F7).
cost: estimated M, actual M

Verdict: rework. F1–F4 are fixed on the branch, then a scoped re-review follows.

- [x] Reviewer independence settled (step 0): delegated. The orchestrator wrote the branch in this session. A fresh sub-agent ran steps 1–4a with `hunt: angle 7 only`. Its 4 findings were re-verified by hand and none was discarded. Its F1, F2, F3 and F4 became F1, F3, F7 and F8 here.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` gave 0 errors and 0 warnings after the rebase onto `main`.
- [x] Implementation audit (steps 1, 2): the acceptance test was re-run verbatim by the delegated reviewer and by the orchestrator, and is green (52 and 178 passed, ruff clean). Tasks 1–6 and decisions 1–14 were met as planned; F4 is a defect in decision 11 itself.
- [x] Correctness hunt (step 3): the host tool path. The orchestrator ran `/code-review` (medium) on `main...feat/EK-004-authority-policy`. It reported 4 findings (F2, F4, F5, F6 here); all were re-verified and none was discarded. Angle 7 ran separately, in the delegated reviewer. Every correctness row is reproduced, except F5, which is traced.
- [x] Consistency audit (step 4): no stale `POLICY_VERSION`, "Task-012" or "until a policy exists" references. ADR-0007:42's "(Task-012)" is an accepted forward reference and is left as is.
- [x] Documentation audit (step 4a): `docs/trust-model.md`, `docs/operating.md`, `docs/source-onboarding.md` and `examples/README.md` are covered, and nothing in `docs/` links to `development/`. No docs build is configured. F8 is the only wording issue.
- [x] Docs-readability pass (step 4b): consciously skipped (optional). The delegated reviewer checked the changed prose against the code.
- [x] Findings recorded (step 5)
- [x] Ticket moved to `5-rework/` (step 6)
- [x] Governing documents reconciled (step 7): the branch carries the ADR-0010, architecture and roadmap edits. F4 amends decision 11 (plan amended inline).
- [x] Impact sweep (step 8): EK-003 reads `in_force`, `required` and `freshness_days`, none of which changes. F4 changes only the CLI. EK-015 is filed for F9.
- [ ] Approval and publish (step 9): pending the re-review.

## History

- 2026-11-18 — created (TO DO). source: chat: migrated from roadmap Task-012 when Brine was set up
- 2026-11-19 — description patched (EK-001 review, step 8): the §13 answers are recorded by EK-014, split from EK-001
- 2026-11-21 — refined. Owner decisions: mechanism now, rows later (no real policy rows ship); `required` and freshness live in this policy (EK-003 depends on it); file at config/policy.toml like sources.toml; reviewer roles recorded, not checked. Re-graded complexity high → medium, cost L → M. Plan written
- 2026-11-21 — TO DO → READY: plan complete
- 2026-11-21 — plan amended at applicability gate (owner-approved routing; 12 non-blocking, 0 blocking): G1/G6/G7 existing tests, repo guard and cwd fixture; G2 policy line outside the table; G3 IRI lookup, tested on real report output; G4 rejected/superseded facts excluded (owner decision); G5 refuse datetime; G8 stale statements in §13 and ADR-0002; G10 refuse prefer-authoritative with no sources; G11 placing the file is the approval; G12 acceptance JSON path kept, duplicate version dropped. G9 folded into EK-003, Q3 added to EK-014
- 2026-11-21 — READY → IN DEVELOPMENT: picked up
- 2026-11-21 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-11-24 — plan amended inline (review F4, owner decision): decision 11 now refuses a missing file named explicitly with --policy; the acceptance step was changed to match
- 2026-11-24 — IN REVIEW → REWORK: review: 4 blocking (F1-F4); F8 fixed inline, F9 -> EK-015, F5-F7 noted
