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
       def parse_options(self, options: dict[str, object], where: str) -> dict[str, object]: ...
       def read(self, path: Path, source: SourceConfig) -> ReadResult: ...
   ```
   - `parse_options` receives every key of the `[[sources]]` entry except the common
     ones. It must raise `ConfigError` on an unknown or invalid key, so unknown keys stay
     refused, and it returns the validated options.
   - `read` is read-only and returns `file_name` and `sha256` of the exact bytes it read.
4. **The common keys are the same for every enabled source:** `id`, `kind`, `enabled`,
   `issuer`, `mapping_version` and `mapping`. `mapping` must include `employee_id`, and
   its fields must come from `FIELD_PREDICATES`, so plugins cannot add properties
   (ontology first). `SourceConfig` gains `options: dict[str, object]`, and `sheet`
   moves into Excel's options (`source.options.get("sheet")`). `sources.toml` is
   unchanged for users.
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
   `file_name` is a model finding, and nothing is saved (exit 2).
9. **An ADR records the contract.** It is the next free number, "Source adapter
   plugins". It covers decisions 1–8, the file-sources-only limit, and that the API
   source-version design is left to EK-007 (owner decision 2026-11-21). ADR-0007's
   header gains a pointer to it.

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

<!-- empty until IN REVIEW -->

## History

- 2026-11-18 — created (TO DO). source: chat: found while checking adapter wiring for a downstream package
- 2026-11-18 — EK-011 review: folded docs item F4 (how a downstream package depends on ek)
- 2026-11-21 — refined. Owner decisions: file sources only (API source-version ADR goes to EK-007); generic `ingest PATH --source-id`, ingest-excel kept. Grades unchanged. Plan written
- 2026-11-21 — TO DO → READY: plan complete
