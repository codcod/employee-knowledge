# ADR-0011: Source adapter plugins

- **Status:** Accepted (2026-11-25). The project owner approved EK-012 and merged it
  (PR #6). First proposed 2026-11-25.
- **Related:** ADR-0003, ADR-0006, ADR-0007. Amends ADR-0007's schema table.

## Context

Architecture §4.1 lists "Other systems" as an extension point, but the code had none.
`config.py` accepted only built-in kinds and parsed only Excel options, `cli.py` hard-wired
the Excel adapter, and nothing discovered adapters. A downstream package could call
`ek.ingest.ingest` from its own CLI, but could not add a source kind that
`employee-knowledge` itself ingests.

The owner decided on 2026-11-21 that the extension point covers file sources only.
Provenance for API sources needs a source version in place of a file hash; that design
goes to the first real API connector (EK-007), where it can be shaped by a real API.

## Decision

1. **Discovery.** A source kind is an entry point in the group
   `employee_knowledge.adapters`; the entry-point name is the kind. Discovery uses
   `importlib.metadata.entry_points`, so there is no new dependency.
2. **Excel registers the same way:** `excel = "ek.adapters.excel:plugin"` in ek's own
   `pyproject.toml`. ek must therefore be installed (`uv sync`, or the wheel) for Excel
   to be found.
3. **Contract.** A plugin is an object with two methods (`ek.adapters.base.AdapterPlugin`,
   which replaces the unused `SourceAdapter`):
   - `parse_options(options, where)` receives every key of the `[[sources]]` entry
     except the common ones, raises `ConfigError` on an unknown or invalid key, and
     returns the validated options.
   - `read(path, source)` is read-only, returns a `ReadResult` with `file_name` and the
     `sha256` of the exact bytes read, and raises `SourceError` when the source cannot
     be read.
4. **Common keys** are `id`, `kind`, `enabled`, `issuer`, `mapping_version` and
   `mapping`, validated by ek for every plugin-kind source, enabled or not. `mapping`
   must include `employee_id`, and its fields must be assertable properties, so a plugin
   cannot add a property (ontology first, architecture §4.4). `SourceConfig` gains
   `options`; Excel's `sheet` moves there. `sources.toml` is unchanged for users.
5. **Placeholders stay.** `confluence`, `jira` and `powerbi` keep their keys and are
   accepted only with `enabled = false`, and only while no plugin registers that kind. A
   plugin registering one of them takes precedence.
6. **Lazy loading, explicit failures.** Only kinds that are configured are loaded. Two
   entry points for one kind are a `ConfigError` naming both distributions; a plugin that
   fails to import is a `ConfigError` naming `<name> = <value>` and the exception type; an
   unregistered kind is "unknown kind". Plugins load while the configuration is parsed.
7. **CLI.** `employee-knowledge ingest PATH --source-id ID [--config]` dispatches by the
   source's kind, with `ingest-excel`'s output and exit codes: 1 on a configuration or
   source error, 2 on a model finding. `ingest-excel` keeps refusing non-Excel sources.
   The summary line says "File sha256".
8. **Provenance and validation are unchanged, and ek checks what a plugin returns.** A
   plugin's `ReadResult` goes through `ek.ingest.ingest` and SHACL like Excel's: a model
   finding aborts the run and nothing is saved. Before that, each with a `SourceError`
   (exit 1, nothing saved):
   - The CLI re-hashes the file and refuses a `sha256` that does not match it, and a
     `file_name` that is not the file's own name. File provenance is ek's to verify, not
     a plugin's to assert (architecture §3.2; owner decision 2026-11-25, EK-012 review
     F2).
   - `ingest` refuses a record whose employee ID is not non-blank, trimmed text, an
     employee ID on two records of one read (the source would contradict itself), a
     value that is not text, and a field the source's `mapping` does not name (EK-012
     review F1).

## Alternatives considered

- **A registry in ek's own code** (a dict of kinds). Downstream packages would have to
  edit `src/ek/` or monkeypatch it at import. Rejected.
- **A `plugins = [...]` list in `sources.toml`.** It puts import paths in configuration
  and repeats what packaging metadata already records. Rejected.
- **Load every registered plugin at start-up.** One broken, unused plugin would break
  every command. Rejected for lazy loading.
- **Design API-source provenance now.** Without a real API to design against, it would be
  guesswork. Deferred to EK-007 (owner decision 2026-11-21).

## Consequences

- A downstream package adds a file source kind with one entry point and no change to ek.
- When an authority policy is loaded, `report`, `report-json` and the `review`
  commands read the source configuration to check the policy's source ids, so they also
  load configured plugins. A broken plugin then makes them exit 1.
- Installed plugin code runs inside ek with ek's permissions. Installing one is a trust
  decision about that code, made by whoever installs it; ek does not sandbox it.
- Plugins see the shared contract only; `ReadResult` stays file-shaped until EK-007.

## Migration

None for users: `sources.toml` is unchanged. Code that read `SourceConfig.sheet` reads
`source.options.get("sheet")`. Code that built `SourceConfig(sheet=...)` passes
`options={"sheet": ...}`.
