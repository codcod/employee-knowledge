---
id: EK-012
title: Add an extension point for third-party source adapters
project: employee-knowledge
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EK-012 — Add an extension point for third-party source adapters

## Outcome

After this ships, a separate package can add a file-based source kind, with its adapter
and its configuration options, by declaring one Python entry point. It then ingests
through `employee-knowledge ingest PATH --source-id ID`, with full provenance and
validation, and without editing `src/ek/`. Built-in Excel ingestion works as before.

## Description

Before this ticket, the seam exists only at library level: an adapter returns
`ReadResult`, and `ek.ingest.ingest` does the rest, so a downstream package can call it
from its own CLI. Three things are closed:

- `ek/config.py` accepts only the built-in kinds (`_KIND_KEYS`) and parses only Excel
  options, and `SourceConfig` has no place for adapter-specific options.
- `ek/cli.py` hard-wires `ExcelAdapter` in `ingest-excel`; there is no generic `ingest`
  that dispatches by kind.
- There is no discovery, so downstream adapters cannot register themselves.

Refined 2026-11-21 (owner decisions):
- **File sources only.** `ReadResult` and the SHACL shapes require `ek:fileName` and
  `ek:sha256`, and plugins must supply both. The source-version provenance that API
  sources need (with its ADR and ontology change) goes to the first real API connector,
  EK-007, where it can be designed against a real API. EK-008 and EK-009 then follow it.
- **CLI shape:** a generic `ingest PATH --source-id ID` dispatches by the source's kind.
  `ingest-excel` stays as it is.

Out of scope: extending the ontology from outside (new attributes still go through the
ontology-first rule); non-file sources (above).

Docs item (folded from EK-011 review, F4): document how a downstream package depends on
ek (a wheel, or `uv add "employee-knowledge @ git+<repo-url>@<tag>"`), alongside the
adapter extension docs.

Soft couplings: EK-011 (packaging; done), EK-007, EK-008 and EK-009 (built-in adapters
should register through the same mechanism, and EK-007 designs non-file provenance),
EK-010 (onboarding docs).

Acceptance: a test package registers a synthetic adapter kind; `sources.toml` accepts
it; one generic CLI command ingests it with full provenance and validation; unknown kinds
are still refused; built-in Excel ingestion is unchanged.

Grades unchanged at refinement (high / medium / M).

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd /Users/nka/Projects/codcod/employee-knowledge   # child path "." (in-tree layout)
git checkout main && git pull --ff-only
git checkout -b feat/EK-012-adapter-plugins
```

Do all work on this branch, with local WIP commits. Publish-gated: no push and no merge
request without the owner's explicit approval (AGENTS.md, rules §0). This is a root-path
child, so tidy the WIP commits into atomic ones before presenting, and keep that history
by default. Before pushing, run
`git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'`; it
must print nothing. Merging is the human's.

### Prerequisite gate (hard)

None: `depends-on: []`. Start from a clean tree on an up-to-date `main`, and check that
`uv run pytest` is green first. Run `uv sync --extra dev` after editing
`pyproject.toml`, so the editable install picks up the new entry point.

### Confirmed design decisions (do not deviate without asking)

1. **Discovery uses the entry-point group `employee_knowledge.adapters`, and the
   entry-point name is the source kind.** Discovery calls
   `importlib.metadata.entry_points(group=...)`, so there is no new dependency.
2. **Built-in Excel registers through the same group.** `pyproject.toml` gets
   `[project.entry-points."employee_knowledge.adapters"]` with `excel =
   "ek.adapters.excel:plugin"`. Built-in and third-party adapters then share one path, as
   the soft coupling to EK-007 to EK-009 asks. The consequence is that ek must be
   installed for Excel to be found, which `uv sync` and the wheel both do.
3. **The plugin contract** is `AdapterPlugin` in `src/ek/adapters/base.py`, and it
   replaces the unused `SourceAdapter` protocol:
   ```python
   class AdapterPlugin(tp.Protocol):
       def parse_options(
           self, options: dict[str, object], where: str
       ) -> dict[str, object]: ...
       def read(self, path: Path, source: SourceConfig) -> ReadResult: ...
   ```
   - `parse_options` receives every key of the `[[sources]]` entry except the common
     ones. It must raise `ConfigError` on an unknown or invalid key, so unknown keys stay
     refused, and it returns the validated options.
   - `read` is read-only and returns `file_name` and `sha256` of the exact bytes it read.
     It raises `SourceError` for a source it cannot read (gate G1).
4. **The common keys are the same for every enabled source:** `id`, `kind`, `enabled`,
   `issuer`, `mapping_version` and `mapping`. `mapping` must include `employee_id`, and
   its fields must come from `FIELD_PREDICATES`, so plugins cannot add properties
   (ontology first). `SourceConfig` gains `options: dict[str, object]`, and `sheet`
   moves into Excel's options (`source.options.get("sheet")`). `sources.toml` is
   unchanged for users. A disabled source of a plugin kind is validated in full, as a
   disabled Excel source is today; placeholder kinds keep only their own keys (gate G3).
5. **The disabled placeholder kinds stay.** `confluence`, `jira` and `powerbi` keep
   their keys in `config.py` and are accepted only with `enabled = false`, and only when
   no plugin registers that kind. A plugin registering one of them, as EK-007 will, takes
   precedence.
6. **Plugins are loaded lazily and failures are explicit.** Only the entry point for a
   kind that is actually configured is loaded. The checks:
   - Two entry points with the same name are a `ConfigError` naming both distributions.
   - A plugin that fails to import is a `ConfigError` naming `<name> = <value>` and the
     exception type.
   - An unknown kind is still "unknown kind".

   Plugins load at parse time, inside `_parse`, which avoids an import cycle between
   `config.py` and the adapters.
7. **The generic `ingest PATH --source-id ID [--config]` command dispatches by kind.**
   Its output and exit codes are the same as `ingest-excel` today: exit 1 on
   `ConfigError` or `SourceError`, and exit 2 on `IngestError`. `ingest-excel` keeps
   refusing non-Excel sources, and both commands share one internal function.
8. **Provenance and validation do not change.** A plugin's `ReadResult` goes through
   `ek.ingest.ingest` and SHACL unchanged, so a missing or malformed `sha256` or
   `file_name` is a model finding, and nothing is saved (exit 2). `ingest` refuses a
   record value whose field is not in the source's `mapping` with a `SourceError`
   (exit 1, nothing saved), so a plugin cannot add properties (gate G1). Amended at
   review (owner sign-off 2026-11-25, F1/F2): the CLI re-hashes the file and refuses a
   `sha256` that does not match or a `file_name` that is not the file's own name; `ingest`
   also refuses a blank, untrimmed or non-str employee ID, an ID on two records of one
   read, and a non-str value, each with `SourceError` (exit 1, nothing saved).
9. **An ADR records the contract.** It is the next free number, "Source adapter
   plugins". It covers decisions 1–8, the file-sources-only limit, and that the API
   source-version design is left to EK-007 (owner decision 2026-11-21). Its
   Consequences note that `report`, `report-json` and `review` also load configured
   plugins, so a broken plugin makes them exit 1 (gate G4). It is ADR-0011, status
   Proposed until merge. ADR-0007's header says "Amended by ADR-0011" (gate G5).
10. **The summary line says "File sha256"** in both commands, not "Workbook sha256"
    (gate G7).

### Tasks

#### Task 1 — Registry

New `src/ek/adapters/registry.py` (about 30 lines):
- `GROUP = "employee_knowledge.adapters"`.
- `load_adapter(kind: str) -> AdapterPlugin | None`, which returns `None` when nothing
  registers the kind and applies decision 6.

#### Task 2 — Contract and config

- `src/ek/adapters/base.py`: `AdapterPlugin` per decision 3, replacing `SourceAdapter`.
  Grep first to confirm nothing uses `SourceAdapter`.
- `src/ek/config.py`:
  - Add `SourceConfig.options` and remove the `sheet` field.
  - In `_parse`, validate the common keys, then either route to the plugin's
    `parse_options` or apply the placeholder rule (decision 5). `_KIND_KEYS` shrinks to
    the three placeholders.

#### Task 3 — Excel as a plugin

`src/ek/adapters/excel.py`:
- A module-level `plugin` object whose `parse_options` accepts only `sheet` (a non-blank
  string) and whose `read(path, source)` returns `ExcelAdapter(path, source).read()`.
- `ExcelAdapter` reads `source.options.get("sheet")`.
- `pyproject.toml` gets the entry point from decision 2.

#### Task 4 — CLI

`src/ek/cli.py`:
- New `ingest` command, per decision 7.
- `ingest-excel` becomes the kind check plus a call to the shared function.

#### Task 5 — Tests

- `tests/test_plugins.py`, unit level: monkeypatch `ek.adapters.registry.entry_points`
  with synthetic `importlib.metadata.EntryPoint` objects. Cover:
  - A synthetic kind with options is accepted.
  - An unknown option is refused.
  - An unknown kind is refused.
  - A duplicate kind is refused, naming both.
  - An import failure is a clear `ConfigError`.
  - A plugin registering `jira` overrides the placeholder.
  - A placeholder kind with `enabled = true` and no plugin is still refused.
- `tests/test_plugins.py`, end-to-end with a real registration:
  - In `tmp_path`, write a synthetic plugin module `ek_test_csv.py`. It reads a synthetic
    CSV with the stdlib `csv` module, takes an option `delimiter`, and sets references
    like `people.csv!row 2`.
  - Write a `ek_test_csv-0.0.0.dist-info/` directory with `METADATA` and an
    `entry_points.txt` containing `csv = ek_test_csv:plugin`.
  - Run `sys.executable -m ek.cli ingest people.csv --source-id csv-src --config ...` in
    a subprocess, with `PYTHONPATH=tmp_path` and `EMPLOYEE_KNOWLEDGE_STORE` in tmp.
  - Assert exit 0. The store has a run with the CSV's `ek:fileName` and its true
    `ek:sha256`, observations with the CSV source references, assertions in the untrusted
    graph only, and validation results on the observations.
  - A variant plugin that returns a bad `sha256` exits 2, and no store file is written.
  - A plugin returning a value field outside the mapping exits 1, nothing written (G1).
  - `ingest-excel` on the CSV source exits 1, with "not an Excel source".
- **Excel unchanged (regression):** ingesting `examples/employees.xlsx` through `ingest`
  and through `ingest-excel` into two fresh stores gives identical assertion URI sets and
  identical summary output, apart from the run id.
- **Existing tests:** update the `SourceConfig(sheet=...)` call sites in
  `tests/test_excel.py` and `tests/test_config.py` to `options={"sheet": ...}`, without
  weakening any assertion. `tests/test_packaging.py` gains a check that the wheel's
  `entry_points.txt` registers `excel`, and the existing from-wheel ingestion test still
  passes.

### Acceptance test

```
uv sync --extra dev
uv run pytest tests/test_plugins.py -v      # all pass
uv run pytest                                # all pass, including test_packaging.py
uv run ruff check . && uv run ruff format --check .

# Manual, synthetic only:
export EMPLOYEE_KNOWLEDGE_STORE="$(mktemp -d)/store.trig"
uv run employee-knowledge ingest examples/employees.xlsx --source-id hr-export --config examples/sources.toml
#   same summary line as ingest-excel ("Run … completed: … observations of … assertions")
uv run employee-knowledge ingest-excel examples/employees.xlsx --source-id hr-export --config examples/sources.toml
#   still works; 0 new assertions (idempotent)
uv run employee-knowledge ingest examples/employees.xlsx --source-id jira-user-directory --config examples/sources.toml
#   exit 1: source is disabled
```

### Docs update (mandatory when user-facing)

- `docs/source-onboarding.md`: a new section, "Adding a source kind from another
  package". It covers:
  - the contract (`parse_options`, `read`), with the entry-point snippet for the
    plugin's `pyproject.toml`;
  - the rules: read-only, file provenance (`file_name` and `sha256` of the bytes read),
    no trust decisions, mapping only to existing ontology fields, and never embedding
    credentials;
  - the onboarding checklist the new kind still needs;
  - how a downstream package depends on ek, as a wheel or with
    `uv add "employee-knowledge @ git+<repo-url>@<tag>"` (folded item F4).
- `docs/source-onboarding.md`: also fix the existing key table, which says `kind` is
  `excel` and lists `sheet` as a common key (gate G5).
- `docs/operating.md`: the `ingest` command, with `ingest-excel` kept as the
  Excel-specific form.
- `development/`:
  - The ADR (decision 9), registered in `development/decisions/README.md`, with the
    pointer in ADR-0007.
  - In architecture §4.1, the "Other systems | Extension point" row links the ADR; in
    §10, add `adapters/registry.py`.
  - Add the file-sources-only note to EK-007's Description at review (impact sweep), not
    on this branch.
- The project keeps no changelog. `docs/` must not link to `development/`.

### Finish (mandatory)

1. Acceptance test green; `uv run pytest` and both ruff checks clean.
2. Docs updated and the ADR registered.
3. Write the summary: files touched, decisions honoured, and anything deferred
   (non-file sources go to EK-007).
4. Suggested commit message:

   ```
   feat(adapters): load source adapters from entry points (EK-012)

   Source kinds register in the employee_knowledge.adapters entry-point
   group; Excel uses it too. sources.toml passes non-common keys to the
   adapter's parse_options, and `employee-knowledge ingest` dispatches by
   kind. File sources only; provenance and validation are unchanged.
   ```

5. Tidy up before presenting: this is a root-path child (`path = "."`), so rebase the WIP
   commits into a few atomic commits.
6. Commit locally on the branch; do not push or open an MR. Move the ticket to
   `4-in-review/` (`pickle ticket move EK-012 in-review --reason "acceptance green"`).

## Review

Reviewed 2026-11-25 on `feat/EK-012-adapter-plugins` (9f4721e, dfbc680; inline fixes bd53058).

- [x] Reviewer independence settled (step 0): **delegated**. The orchestrator wrote the branch, so a fresh sub-agent with no hand in it ran steps 1 to 4a (hunt: angle 7 only). The orchestrator re-verified its 4 findings: its F1 (false sha256) by its reproduction, its F4 by a second reproduction, its F2 and F3 by reading the code.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` warned that the branch had the ticket in `3-in-development`. Rebased onto `main`, and it is now clean. The reviewer's own run was also clean.
- [x] Implementation audit (steps 1, 2): Tasks 1 to 5 are met and decisions 1 to 10 are honoured. The acceptance test was re-run verbatim on synthetic data, and the manual output matched. `uv run pytest`: 236 passed. `ruff check` and `ruff format --check` are clean.
- [x] Correctness hunt (step 3): **host tool path**. The top-level session ran `/code-review medium` on `main...feat/EK-012-adapter-plugins`, which reported 8 findings. Two were discarded on re-verification:
  - Disabled plugin-kind sources still load their plugin, so an uninstalled plugin breaks every command. This is the owner-approved gate G3, with the consequence recorded in ADR-0011 (G4).
  - `excel` resolves only through installed metadata. This is decision 2's stated consequence, recorded in the ADR.

  The tool does not review for security, so the delegated reviewer ran angle 7 separately. F1 and F2 are reproduced; F3 to F6 are traced.
- [x] Consistency audit (step 4): no stale `SourceAdapter`, `_KIND_KEYS`, `.sheet` or "Workbook sha256" references remain. ADR-0011's consequence wording was fixed (F8). Rich markup and control characters in plugin-supplied text are already EK-015's (gate G2 note).
- [x] Documentation audit (step 4a):
  - `docs/source-onboarding.md` has the new section, the fixed key table and the dependency docs (F4 from EK-011). `docs/operating.md` covers `ingest`.
  - The anchors resolve, and no `docs/` page links to `development/`.
  - No docs build is configured. F7 was fixed inline.
- [x] Docs-readability pass (step 4b): skipped. It is optional, and the changed prose was reviewed in the docs audit.
- [x] Findings recorded with severity, class and disposition; the summary and cost lines are below (step 5).
- [x] Ticket moved to `tickets/5-rework/` with a `## History` line (step 6a).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | blocking | correctness | — | `ingest` trusts a plugin's records. Duplicate employee IDs in one read are accepted, so the source contradicts itself; Excel quarantines them. A blank ID gives a `ValueError` traceback, a non-str value an `AttributeError`, and a padded ID an `IngestError` (exit 2, reported as a system fault) | Reproduced by calling `ingest()` directly with synthetic records: `dup id: ACCEPTED 2 assertions`; `blank id: ValueError issuer and employee_id must not be empty`; `int value: AttributeError 'int' object has no attribute 'strip'`. The padded ID came from the reviewer's `probe.py` | Check each record at the top of `ingest`: the ID is a non-blank, trimmed str, no ID appears twice, and values are str. Otherwise raise `SourceError` (exit 1, nothing saved). Add regression tests |
| F2 | blocking | correctness | — | A plugin's well-formed but false `sha256` is stored as the file's hash, exit 0, and an absolute `file_name` is accepted. That fabricates file provenance (§3.2). EK-012 decision 8 left this to SHACL, which checks the format only. The owner signed off on changing decision 8 (2026-11-25) | Reproduced (reviewer, `scratchpad/review-ek012/sha/`): a plugin returning `"0"*64` exits 0 and the store holds `sha256 "0000…"`, while the real hash is `19c8226f…`. `ReadResult("/Users/someone/HR/secret.csv", …)` ingests | In `cli._ingest`, refuse with `SourceError` unless `result.sha256` equals the sha256 of the file's bytes and `result.file_name == path.name`. Add a lying-sha plugin variant and a test |
| F3 | non-blocking | correctness | noted | A plugin exception other than `SourceError` or `ConfigError` (from `read` or `parse_options`), or a non-dict options return, gives a traceback instead of exit 1. Nothing is saved, and typer prints no locals | Traced: `cli._ingest` catches only `ConfigError`, `SourceError` and `IngestError`, and `config._parse` calls `parse_options` unwrapped. The contract (decision 3, gate G1) requires `SourceError`/`ConfigError` | Wrap plugin calls, if third-party plugins turn out to be careless |
| F4 | non-blocking | design | noted | An entry point that names a class instead of an instance loads fine, then fails later with a `TypeError` traceback | Traced: `registry.load_adapter` returns `ep.load()` unchecked | Check that `parse_options` and `read` are callable after loading |
| F5 | non-blocking | correctness | noted | A directory as the path gives an `IsADirectoryError` traceback. This existed already in `ingest-excel` and `ingest` inherits it | Traced: `SourceFile` has no `dir_okay=False`, and `ExcelAdapter.read` calls `read_bytes()` outside its caught exceptions | `dir_okay=False` on `SourceFile` |
| F6 | non-blocking | design | noted | `_ingest` looks the plugin up again after config parsing has loaded it, and relies on "enabled sources always have a plugin" | `src/ek/cli.py` `_ingest` | Carry the resolved plugin on the parsed source, if a second lookup ever matters |
| F7 | non-blocking | docs-gap | fixed inline | The plugin rules banned employee data in `SourceError` messages but not in quarantine reasons or record references, which are printed too | `docs/source-onboarding.md` "Rules for a source kind"; `src/ek/cli.py` prints both | Clause added (bd53058) |
| F8 | non-blocking | spec-unclear | fixed inline | ADR-0011 said `report`, `report-json` and `review` always load plugins. They do so only when a policy is loaded | `src/ek/cli.py` `_policy`: `load_sources` runs only `if path.exists()` | Reworded (bd53058) |

### Rework fix record — round 1 (commit a9fd653)

- F1: `ingest._check_records` refuses a record whose employee ID is not non-blank, trimmed str, an ID on two records of one read, a non-str value, and an unmapped field. Each is a `SourceError` naming source references only. Tests: `test_ingest_refuses_unusable_records` (7 cases).
- F2: `cli._check_file` re-hashes the file after `read` and refuses a mismatched `sha256` or a `file_name` other than `path.name`. Tests: `test_plugin_file_provenance_is_verified` (lie-sha, abs-name). The former bad-sha exit-2 test became `test_plugin_model_finding_aborts_and_saves_nothing`, which uses a blank source reference, so the model-finding path is still covered.
- Decision 8 amended in the plan and ADR-0011. `docs/source-onboarding.md` rules updated ("File provenance", "Usable records").
- Without the fix, 8 of the new tests fail. With it, `uv run pytest` gives 245 passed, and both ruff checks are clean.

### Scoped re-review — round 1

Re-reviewed 2026-11-25 on `a9fd653` (fix), with the inline fix `fe5f881`.

- [x] Reviewer independence (step 0): **delegated**. A fresh sub-agent ran steps 1 to 4a with a one-pass hunt over `git show a9fd653` only, which is the scoped re-review rule. The orchestrator re-verified F9 by reading the docs and the code. F10 was the reviewer's reproduction, and the orchestrator traced it in `ingest.digest`.
- [x] Stale-branch check (step 0a): `pickle doctor` clean.
- [x] F1 closed: the 6 new cases fail against the pre-fix code and pass on `a9fd653`. F2 closed: the lie-sha plugin exited 0 before the fix and exits 1 now.
- [x] Acceptance re-run verbatim on synthetic data. `uv run pytest`: 245 passed. Ruff checks clean.
- [x] Consistency and docs: ADR-0011 decision 8, the plan's amended decision 8 and the onboarding rules agree. No `docs/` link points to `development/`.
- [x] Docs-readability pass (step 4b): skipped. It is optional, and the prose was reviewed in the docs audit.
- [x] Ticket moved to `tickets/6-done/` (step 6b).
- [x] Other references (step 7): ADR-0011, ADR-0007 pointer, architecture §4.1 and §10 updated on the branch. Board regenerated by the move.
- [x] Impact sweep (step 8): EK-007 Description patched (entry-point registration; owns non-file provenance). History notes added to EK-008, EK-009 and EK-010. EK-015 already holds the G2 note.

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F9 | non-blocking | spec-unclear | fixed inline | "Usable records" read as if a plugin quarantines only the later duplicate, which keeps one value and so picks a winner (§3.5). Excel keeps neither. The new message "adapter returned one employee ID at A, B" read as one ID | `docs/source-onboarding.md` "Usable records"; `src/ek/ingest.py` `_check_records`; `src/ek/adapters/excel.py` "keep neither" | Docs say to quarantine every record that shares an ID. The message now reads "the same employee ID at A and B" (fe5f881) |
| F10 | non-blocking | correctness | noted | A non-str `source_reference` raises a `TypeError` traceback from `digest()` instead of exit 1. An `OSError` while `_check_file` re-reads the file is uncaught. Nothing is saved in either case. Same family as F3 | Reproduced (reviewer): `EmployeeRecord("E-1", {"department": "Eng"}, 7)` gives `TypeError: sequence item 2: expected str instance, int found` | Require a str reference in `_check_records`, together with F3, if plugins prove careless |

Dispositions: blocking 2 (F1, F2), both fixed in round 1 · fixed inline 3 (F7, F8, F9) · folded 0 · noted 5 (F3, F4, F5, F6, F10) · new ticket 0.
cost: estimated M, actual M

### First review summary

Dispositions: blocking 2 (F1, F2) · fixed inline 2 (F7, F8) · folded 0 · noted 4 (F3, F4, F5, F6) · new ticket 0.
cost: estimated M, actual M

## History

- 2026-11-18 — created (TO DO). source: chat: found while checking adapter wiring for a downstream package
- 2026-11-18 — EK-011 review: folded docs item F4 (how a downstream package depends on ek)
- 2026-11-21 — refined. Owner decisions: file sources only (API source-version ADR goes to EK-007); generic `ingest PATH --source-id`, ingest-excel kept. Grades unchanged. Plan written
- 2026-11-21 — TO DO → READY: plan complete
- 2026-11-25 — applicability gate (independent sub-agent): no blocking findings; 7 non-blocking. G1, G3, G4, G5, G7 inline; G2 noted on EK-015; G6 note-and-close (hand-built EntryPoints have no dist; stale egg-info would show a false duplicate if distributions() were iterated). Owner approved routing
- 2026-11-25 — plan amended inline: decisions 3, 4, 8, 9 and new 10 (plugin read raises SourceError; ingest refuses unmapped fields; disabled plugin sources fully validated; ADR-0011 Proposed with G4 consequence and ADR-0007 'amended by' pointer; 'File sha256'), docs step fixes the existing key table, one extra test
- 2026-11-25 — READY → IN DEVELOPMENT: picked up
- 2026-11-25 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-11-25 — IN REVIEW → REWORK: 2 blocking findings (F1 plugin record invariants, F2 unverified file provenance)
- 2026-11-25 — plan amended inline: decision 8 now has ek verify file provenance (re-hash, own file name) and refuse unusable plugin records, per the owner's sign-off on review F2 and blocking F1
- 2026-11-25 — REWORK → IN REVIEW: findings fixed
- 2026-11-25 — IN REVIEW → DONE: re-review clean: F1, F2 fixed; fixed inline 3 (F7, F8, F9); noted 5 (F3-F6, F10); no new tickets
